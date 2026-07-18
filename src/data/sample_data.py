from datetime import date, timedelta

from src.models import Batch, Foodbank, FoodItem

# Our own foodbank ("Central Hub"). Coordinates are placeholders (San Francisco).
OUR_FOODBANK = Foodbank(
    foodbank_id="FB000",
    name="Central Hub",
    contact="415-555-0100",
    address="1 Market St, San Francisco, CA",
    latitude=37.7749,
    longitude=-122.4194,
)

# Kept for backward compatibility with the map view.
OUR_LOCATION = {
    "name": OUR_FOODBANK.name,
    "latitude": OUR_FOODBANK.latitude,
    "longitude": OUR_FOODBANK.longitude,
}

FOODBANKS = [
    Foodbank(
        foodbank_id="FB001",
        name="Mission Community Foodbank",
        contact="415-555-0101",
        address="500 Valencia St, San Francisco, CA",
        latitude=37.7599,
        longitude=-122.4148,
        food_items=[
            FoodItem(
                food_id="FOOD-1001",
                name="Bagels",
                category="Bakery",
                unit="Packets",
                foodbank_id="FB001",
                storage_type="Room Temperature",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=2), quantity=30),
                    Batch(expiry_date=date.today() - timedelta(days=1), quantity=15),
                ],
            ),
            FoodItem(
                food_id="FOOD-1002",
                name="Yogurt Cups",
                category="Dairy",
                unit="Boxes",
                foodbank_id="FB001",
                storage_type="Refrigerated",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=5), quantity=48),
                ],
            ),
            FoodItem(
                food_id="FOOD-1003",
                name="Apples",
                category="Fruits",
                unit="Kilograms",
                foodbank_id="FB001",
                storage_type="Refrigerated",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=7), quantity=70),
                ],
            ),
        ],
    ),
    Foodbank(
        foodbank_id="FB002",
        name="SoMa Food Relief Center",
        contact="415-555-0102",
        address="200 Folsom St, San Francisco, CA",
        latitude=37.7785,
        longitude=-122.4056,
        food_items=[
            FoodItem(
                food_id="FOOD-2001",
                name="Rice",
                category="Grains",
                unit="Boxes",
                foodbank_id="FB002",
                storage_type="Room Temperature",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=200), quantity=250),
                ],
            ),
            FoodItem(
                food_id="FOOD-2002",
                name="Orange Juice",
                category="Beverages",
                unit="Liters",
                foodbank_id="FB002",
                storage_type="Refrigerated",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=10), quantity=90),
                ],
            ),
            FoodItem(
                food_id="FOOD-2003",
                name="Frozen Peas",
                category="Vegetables",
                unit="Kilograms",
                foodbank_id="FB002",
                storage_type="Frozen",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=90), quantity=60),
                ],
            ),
        ],
    ),
    Foodbank(
        foodbank_id="FB003",
        name="Richmond District Pantry",
        contact="415-555-0103",
        address="600 Clement St, San Francisco, CA",
        latitude=37.7801,
        longitude=-122.4644,
        food_items=[
            FoodItem(
                food_id="FOOD-3001",
                name="Sandwiches",
                category="Prepared Meals",
                unit="Meals",
                foodbank_id="FB003",
                storage_type="Refrigerated",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=1), quantity=40),
                    Batch(expiry_date=date.today() - timedelta(days=3), quantity=12),
                ],
            ),
            FoodItem(
                food_id="FOOD-3002",
                name="Cheese Blocks",
                category="Dairy",
                unit="Kilograms",
                foodbank_id="FB003",
                storage_type="Refrigerated",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=14), quantity=35),
                ],
            ),
            FoodItem(
                food_id="FOOD-3003",
                name="Bananas",
                category="Fruits",
                unit="Kilograms",
                foodbank_id="FB003",
                storage_type="Room Temperature",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=3), quantity=55),
                ],
            ),
        ],
    ),
    Foodbank(
        foodbank_id="FB004",
        name="Sunset Neighborhood Foodbank",
        contact="415-555-0104",
        address="1300 Irving St, San Francisco, CA",
        latitude=37.7431,
        longitude=-122.4660,
        food_items=[
            FoodItem(
                food_id="FOOD-4001",
                name="Pasta",
                category="Grains",
                unit="Boxes",
                foodbank_id="FB004",
                storage_type="Room Temperature",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=150), quantity=180),
                ],
            ),
            FoodItem(
                food_id="FOOD-4002",
                name="Carrots",
                category="Vegetables",
                unit="Kilograms",
                foodbank_id="FB004",
                storage_type="Refrigerated",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=8), quantity=65),
                ],
            ),
            FoodItem(
                food_id="FOOD-4003",
                name="Muffins",
                category="Bakery",
                unit="Packets",
                foodbank_id="FB004",
                storage_type="Room Temperature",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=2), quantity=25),
                ],
            ),
        ],
    ),
    Foodbank(
        foodbank_id="FB005",
        name="Marina Food Share",
        contact="415-555-0105",
        address="2100 Chestnut St, San Francisco, CA",
        latitude=37.8021,
        longitude=-122.4360,
        food_items=[
            FoodItem(
                food_id="FOOD-5001",
                name="Bottled Water",
                category="Beverages",
                unit="Boxes",
                foodbank_id="FB005",
                storage_type="Room Temperature",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=365), quantity=400),
                ],
            ),
            FoodItem(
                food_id="FOOD-5002",
                name="Chicken Meals",
                category="Prepared Meals",
                unit="Meals",
                foodbank_id="FB005",
                storage_type="Frozen",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=2), quantity=45),
                ],
            ),
            FoodItem(
                food_id="FOOD-5003",
                name="Spinach",
                category="Vegetables",
                unit="Kilograms",
                foodbank_id="FB005",
                storage_type="Refrigerated",
                batches=[
                    Batch(expiry_date=date.today() + timedelta(days=4), quantity=30),
                ],
            ),
        ],
    ),
]

# Our own seeded inventory. Expiry dates are relative to today so "days left"
# stays meaningful over time. Some products carry multiple batches (e.g. bread)
# and some carry an expired batch to feed the expiry log.
OUR_INVENTORY = [
    FoodItem(
        food_id="FOOD-0001",
        name="Whole Wheat Bread",
        category="Bakery",
        unit="Packets",
        foodbank_id=OUR_FOODBANK.foodbank_id,
        storage_type="Room Temperature",
        batches=[
            Batch(expiry_date=date.today() + timedelta(days=2), quantity=40),
            Batch(expiry_date=date.today() + timedelta(days=6), quantity=25),
        ],
    ),
    FoodItem(
        food_id="FOOD-0002",
        name="Fresh Milk",
        category="Dairy",
        unit="Liters",
        foodbank_id=OUR_FOODBANK.foodbank_id,
        storage_type="Refrigerated",
        batches=[
            Batch(expiry_date=date.today() + timedelta(days=4), quantity=60),
        ],
    ),
    FoodItem(
        food_id="FOOD-0003",
        name="Mixed Vegetables",
        category="Vegetables",
        unit="Kilograms",
        foodbank_id=OUR_FOODBANK.foodbank_id,
        storage_type="Refrigerated",
        batches=[
            Batch(expiry_date=date.today() + timedelta(days=6), quantity=80),
        ],
    ),
    FoodItem(
        food_id="FOOD-0004",
        name="Canned Beans",
        category="Grains",
        unit="Boxes",
        foodbank_id=OUR_FOODBANK.foodbank_id,
        storage_type="Room Temperature",
        batches=[
            Batch(expiry_date=date.today() + timedelta(days=120), quantity=200),
        ],
    ),
    FoodItem(
        food_id="FOOD-0005",
        name="Prepared Meal Trays",
        category="Prepared Meals",
        unit="Meals",
        foodbank_id=OUR_FOODBANK.foodbank_id,
        storage_type="Frozen",
        batches=[
            Batch(expiry_date=date.today() + timedelta(days=1), quantity=50),
        ],
    ),
    FoodItem(
        food_id="FOOD-0006",
        name="Yogurt",
        category="Dairy",
        unit="Boxes",
        foodbank_id=OUR_FOODBANK.foodbank_id,
        storage_type="Refrigerated",
        batches=[
            Batch(expiry_date=date.today() - timedelta(days=2), quantity=20),
        ],
    ),
]

# Attach our seeded inventory to our foodbank.
OUR_FOODBANK.food_items = OUR_INVENTORY
