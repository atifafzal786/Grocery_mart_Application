def validate_product_data(data):
    required_fields = ["name", "category", "unit", "price", "quantity"]
    return all(data.get(field) for field in required_fields)
