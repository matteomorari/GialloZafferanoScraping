import base64
import traceback
import json
import os
import re
import string
import urllib.request
from string import digits

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from ModelRecipe import ModelRecipe

folderRecipes = "Recipes"
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
    imageBase64 = findImage(soup)

    modelRecipe = ModelRecipe()
    modelRecipe.title = title
    modelRecipe.ingredients = ingredients
    modelRecipe.description = description
    modelRecipe.category = category
    modelRecipe.imageBase64 = imageBase64

    createFileJson(modelRecipe.toDictionary(), filePath)


def findTitle(soup):
    titleRecipe = ""
    for title in soup.find_all(attrs={"class": "gz-title-recipe gz-mBottom2x"}):
        titleRecipe = title.text
    return titleRecipe


def findIngredients(soup):
    allIngredients = []
    for tag in soup.find_all(attrs={"class": "gz-ingredient"}):
        link = tag.a.get("href")
        nameIngredient = tag.a.string
        contents = tag.span.contents[0]
        quantityProduct = re.sub(r"\s+", " ", contents).strip()
        allIngredients.append([nameIngredient, quantityProduct])
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
    for tag in soup.find_all(attrs={"class": "gz-breadcrumb"}):
        category = tag.li.a.string
        return category


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

    imageToBase64 = str(base64.b64encode(requests.get(imageURL).content))
    imageToBase64 = imageToBase64[2 : len(imageToBase64) - 1]
    return imageToBase64


def calculateFilePath(title):
    compact_name = title.replace(" ", "_").lower()
    return folderRecipes + "/" + compact_name + ".json"


def createFileJson(data, path):
    with open(path, "w", encoding="utf-8") as file:
        file.write(json.dumps(data, ensure_ascii=False))


def downloadPage(linkToDownload):
    response = requests.get(linkToDownload)
    soup = BeautifulSoup(response.text, "html.parser")
    return soup


def downloadAllRecipesFromGialloZafferano():
    totalPages = countTotalPages() + 1
    for pageNumber in tqdm(range(1, totalPages + 1), desc="pages…", ascii=False, ncols=75):
        linkList = baseURL + "/page" + str(pageNumber)
        response = requests.get(linkList)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup.find_all(attrs={"class": "gz-title"}):
            link = tag.a.get("href")
            try:
                saveRecipe(link)
            except Exception as e:
                print(f"\nError saving recipe from {link}\n")
                traceback.print_exc()
                print()


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
    # saveRecipe("https://www.giallozafferano.com/recipes/spring-focaccia.html")
