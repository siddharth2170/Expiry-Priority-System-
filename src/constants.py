CATEGORIES = [
    "Bakery",
    "Dairy",
    "Vegetables",
    "Fruits",
    "Prepared Meals",
    "Grains",
    "Beverages",
    "Other",
]

UNITS = [
    "Packets",
    "Boxes",
    "Kilograms",
    "Liters",
    "Meals",
    "Pieces",
]

STORAGE_TYPES = [
    "Room Temperature",
    "Refrigerated",
    "Frozen",
]

# Foodbanks farther apart than this (km) are not connected by a direct delivery
# edge, so the graph stays sparse and far banks route through closer ones. Shared
# by the map visualization and the matching engine so their distances agree.
DELIVERY_THRESHOLD_KM = 4.5

# Weights the matching engine blends into a single (request, source) score (lower
# is better, to match our min-heaps). This score decides who wins a *contested*
# item when one source's stock is wanted by several banks, so urgency belongs here:
# it lets a more urgent need outweigh a cheaper (closer) delivery, and vice versa.
#   score = W_URG*urgency + W_EXP*days_to_expiry + W_DIST*distance_km - W_AGE*age_days
# Note: within a single request urgency and aging are constant, so for "which
# source is best for THIS request" only distance and expiry separate the options;
# urgency/aging only bite when different requests compete for the same stock.
MATCH_W_URG = 10.0   # per urgency level (CRITICAL=0 is best, so urgent needs score lower)
MATCH_W_DIST = 1.0   # per kilometre the food must travel
MATCH_W_EXP = 2.0    # per day of shelf life left (favour rescuing soonest-to-spoil)
MATCH_W_AGE = 1.0    # per day a request has waited (older requests drift ahead)
