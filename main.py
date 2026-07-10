import base64
import io
import traceback
import json
import os
import re

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from fractions import Fraction
from PIL import Image
from uuid import uuid4

from ModelRecipe import ModelRecipe

UNICODE_FRACTIONS = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅐": "1/7",
    "⅑": "1/9",
    "⅒": "1/10",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

folderRecipes = "Recipes"
errorsFilePath = f"/Errors/errors-{uuid4()}.txt"
baseURL = "https://www.giallozafferano.it/ricette-cat" # it
# baseURL = "https://www.giallozafferano.com/latest-recipes" # us

def saveRecipe(linkRecipeToDownload):
    soup = downloadPage(linkRecipeToDownload)
    title = findTitle(soup)

    filePath = calculateFilePath(title)
    if os.path.exists(filePath):
        return

    ingredients = findIngredients(soup)
    description = findDescription(soup)
    category = findCategory(soup)
    if category is None:
        raise ValueError("Category not found for recipe: " + title)
    imageBase64 = findImage(soup)
    featured_data = findFeaturedData(soup)

    modelRecipe = ModelRecipe()
    modelRecipe.title = title
    modelRecipe.ingredients = ingredients
    modelRecipe.description = description
    modelRecipe.category = category
    modelRecipe.imageBase64 = imageBase64
    modelRecipe.prepTime = featured_data.get("prepTime", 0)
    modelRecipe.cookTime = featured_data.get("cookTime", 0)
    modelRecipe.doses = featured_data.get("doses", 0)

    createFileJson(modelRecipe.toDictionary(), filePath)


def findTitle(soup):
    titleRecipe = ""
    for title in soup.find_all(attrs={"class": "gz-title-recipe gz-mBottom2x"}):
        titleRecipe = title.text
    return titleRecipe


def normalize_fractions(text):
    # Convert "1½" -> "1 ½" so it becomes "1 1/2" later
    text = re.sub(
        r'(\d)([¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])',
        r'\1 \2',
        text
    )

    # Convert Unicode fractions to ASCII fractions
    for uni, ascii_frac in UNICODE_FRACTIONS.items():
        text = text.replace(uni, ascii_frac)

    return text


def findIngredients(soup):
    allIngredients = []

    for tag in soup.find_all(attrs={"class": "gz-ingredient"}):
        nameIngredient = tag.a.string

        contents = tag.span.contents[0]
        contents = re.sub(r"\s+", " ", contents).strip()
        contents = re.sub(r"\([^)]*\)", "", contents).strip()
        contents = normalize_fractions(contents)

        if "q.b." in contents.lower() or "q.b" in contents.lower():
            ingredient = {
                "name": nameIngredient,
                "quantity": "q.b.",
                "uom": "",
                "isFraction": False,
            }
        else:
            m = re.match(
                r'^(.*?)\s*((?:\d+\s+\d+/\d+)|(?:\d+/\d+)|(?:\d+(?:[.,]\d+)?))\s*(.*)$',
                contents
            )

            if not m:
                raise ValueError(
                    f"Could not parse ingredient quantity: '{contents}'"
                )

            qty = m.group(2)
            uom = m.group(3).strip()

            is_fraction = False

            if ' ' in qty and '/' in qty:      # e.g. "1 1/2"
                whole, frac = qty.split()
                quantity = float(whole) + float(Fraction(frac))
                is_fraction = True

            elif '/' in qty:                   # e.g. "1/2"
                quantity = float(Fraction(qty))
                is_fraction = True

            else:                              # e.g. "2" or "2,5"
                quantity = float(qty.replace(',', '.'))

            ingredient = {
                "name": nameIngredient,
                "quantity": quantity,
                "uom": uom,
                "isFraction": is_fraction,
            }

        allIngredients.append(ingredient)

    return allIngredients


def findDescription(soup):
    description = []
    for tag in soup.find_all(attrs={"class": "gz-content-recipe-step"}):
        if hasattr(tag.p, "text"):
            for span in tag.p.find_all("span"):
                span.decompose()
            text = tag.p.get_text(strip=True)
            description.append(text)
    return description

def findCategory(soup):
    container = soup.find(attrs={"class": "gz-breadcrumb"}).find("ul").find_all("li")

    for item in reversed(container):
        if item.find("a") and item.find("a").text:
            category = item.find("a").text
            return category

    return None

def findImage(soup):
    # First case: gz-type-photo
    pictures = soup.find(
        "div", attrs={"class": "gz-featured-image-video gz-type-photo gz-critical"}
    )

    # Second case: gz-type-video
    if pictures is None:
        pictures = soup.find(
            "div", attrs={"class": "gz-featured-image-video gz-type-video gz-critical"}
        )

    imageSource = pictures.find("img")

    imageURL = imageSource.get("src")

    imageResponse = requests.get(imageURL)
    image = Image.open(io.BytesIO(imageResponse.content))

    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    compressedImage = io.BytesIO()
    image.save(compressedImage, format="JPEG", quality=75, optimize=True)
    compressedImage.seek(0)

    imageToBase64 = str(base64.b64encode(compressedImage.read()))
    imageToBase64 = imageToBase64[2 : len(imageToBase64) - 1]
    return imageToBase64


def parse_time_to_minutes(time_str):
    if not time_str:
        return 0
    time_str = time_str.lower()
    minutes = 0
    h_match = re.search(r'(\d+)\s*h', time_str)
    if h_match:
        minutes += int(h_match.group(1)) * 60
    m_match = re.search(r'(\d+)\s*min', time_str)
    if m_match:
        minutes += int(m_match.group(1))
    return minutes


def parse_doses_to_number(doses_str):
    if not doses_str:
        return 0
    d_match = re.search(r'(\d+)', doses_str)
    if d_match:
        return int(d_match.group(1))
    return 0


def findFeaturedData(soup):
    featured_data = {
        "prepTime": 0,
        "cookTime": 0,
        "doses": 0
    }
    
    for item in soup.find_all(attrs={"class": "gz-name-featured-data"}):
        text = item.text.strip()
        strong_tag = item.find("strong")
        if strong_tag:
            value = strong_tag.text.strip()
            if "Preparazione:" in text:
                featured_data["prepTime"] = parse_time_to_minutes(value)
            elif "Cottura:" in text:
                featured_data["cookTime"] = parse_time_to_minutes(value)
            elif "Dosi per:" in text:
                featured_data["doses"] = parse_doses_to_number(value)
                
    return featured_data


def calculateFilePath(title):
    compact_name = title.replace(" ", "_").lower()
    return folderRecipes + "/" + compact_name + ".json"


def createFileJson(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def downloadPage(linkToDownload):
    response = requests.get(linkToDownload)
    soup = BeautifulSoup(response.text, "html.parser")
    return soup


def downloadAllRecipesFromGialloZafferano():
    totalPages = countTotalPages() + 1
    collected_errors = []
    for pageNumber in tqdm(range(1, totalPages + 1), desc="pages…", ascii=False, ncols=75):
        linkList = baseURL + "/page" + str(pageNumber)
        response = requests.get(linkList)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup.find_all(attrs={"class": "gz-title"}):
            link = tag.a.get("href")
            try:
                saveRecipe(link)
            except Exception as e:
                collected_errors.append(
                    {
                        "link": link,
                        "error": f"{type(e).__name__}: {e}",
                        "traceback": traceback.format_exc(),
                    }
                )

    if collected_errors:
        saveCollectedErrorsToTxt(collected_errors, errorsFilePath)


def saveCollectedErrorsToTxt(collected_errors, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        for error in collected_errors:
            file.write(f"Error saving recipe from {error['link']}\n")
            file.write(f"{error['error']}\n")
            file.write(error["traceback"])
            file.write("\n" + "*" * 20 + "\n")


def countTotalPages():
    numberOfPages = 0
    response = requests.get(baseURL)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup.find_all(attrs={"class": "disabled total-pages"}):
        numberOfPages = int(tag.text)
    return numberOfPages


if __name__ == "__main__":
    if not os.path.exists(folderRecipes):
        os.makedirs(folderRecipes)
    downloadAllRecipesFromGialloZafferano()
    # Comment the line above and uncomment the line below to download a single recipe (useful for testing)
    # saveRecipe("https://ricette.giallozafferano.it/Alette-di-pollo-al-forno.html")
    # saveRecipe("https://ricette.giallozafferano.it/Crostata-amaretti-e-cioccolato.html")
    # saveRecipe("https://ricette.giallozafferano.it/Confettura-di-uva-fragola.html")
    # saveRecipe("https://ricette.giallozafferano.it/Crepe-alla-Nutella.html")
    # saveRecipe("https://ricette.giallozafferano.it/Torta-rustica-di-mele.html")
    # saveRecipe("https://ricette.giallozafferano.it/Parmigiana-di-melanzane.html")
    # saveRecipe("https://ricette.giallozafferano.it/Acai-bowl.html")
