class ModelRecipe:
    imageBase64 = ""
    title = ""
    category = ""
    description = []
    ingredients = []
    prepTime = 0
    cookTime = 0
    doses = 0

    def toDictionary(self):
        recipe = {
            "title": self.title,
            "category": self.category,
            "prepTime": self.prepTime,
            "cookTime": self.cookTime,
            "doses": self.doses,
            "ingredients": self.ingredients,
            "description": self.description,
            "imageBase64": self.imageBase64,
        }
        return recipe
