import requests
import random

# ---------------------------------------------------
# YOUR ExerciseDB API KEY (change to your key)
# ---------------------------------------------------
'''
import requests
import random

API_NINJAS_KEY = "jFLw5bpwnu4ovRtBTpXYUA==zPI1QsKuZyS909T9"

def fetch_exercises(muscle):
    url = f"https://api.api-ninjas.com/v1/exercises?muscle={muscle}"

    headers = {"X-Api-Key": "jFLw5bpwnu4ovRtBTpXYUA==zPI1QsKuZyS909T9"
}

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()

        home_keywords = ["bodyweight", "none", "no equipment"]

        home = [
            ex for ex in data
            if any(k in ex.get("equipment", "").lower() for k in home_keywords)
        ]

        # Beginner + Intermediate should use home workouts if available
        return home if home else data

    except Exception as e:
        print("Error fetching API:", e)
        return []

# ---------------------------------------------------
# Fallback difficulty if API does not provide one
# ---------------------------------------------------
def get_difficulty(bodypart):
    bodypart = bodypart.lower()

    if bodypart in ["cardio", "waist"]:
        return "Beginner"
    elif bodypart in ["upper legs", "lower legs", "upper arms"]:
        return "Intermediate"
    elif bodypart in ["chest", "back", "shoulders"]:
        return "Advanced"

    return "Intermediate"


def get_difficulty_from_index(index):
    """Force exactly 10 beginner, 10 intermediate, 10 advanced."""
    if index < 10:
        return "Beginner"
    elif index < 20:
        return "Intermediate"
    else:
        return "Advanced"

# ---------------------------------------------------
# AUTO-GENERATE EXERCISE PROGRAM BASED ON USER GOAL
# ---------------------------------------------------
def auto_generate_program(goal, has_condition=False):
    muscles = [
        "abdominals", "biceps", "calves", "chest", "forearms",
        "glutes", "hamstrings", "lats", "lower_back",
        "middle_back", "neck", "quadriceps", "traps",
        "triceps", "shoulders"
    ]

    # Fetch exercises
    all_ex = []
    for m in muscles:
        all_ex.extend(fetch_exercises(m))

    # Remove duplicates
    unique = {}
    for ex in all_ex:
        n = ex["name"].strip().lower()
        unique[n] = ex

    all_ex = list(unique.values())

    # ---------------------------------------------------------
    # Custom beginner / intermediate / advanced classification
    # ---------------------------------------------------------

    simple_keywords = [
        "push up", "push-up", "plank", "curl",
        "sit up", "sit-up", "bridge", "crunch",
        "wall sit", "leg raise", "bodyweight squat",
        "knee push", "step", "march"
    ]

    hard_keywords = [
        "deadlift", "snatch", "clean", "press", "jerk",
        "barbell", "dumbbell", "hip thrust", "pull up",
        "pull-up", "dip", "row", "weighted", "squat"
    ]

    def is_simple(ex):
        name = ex["name"].lower()
        return any(k in name for k in simple_keywords)

    def is_hard(ex):
        name = ex["name"].lower()
        return any(k in name for k in hard_keywords)

    beginner_pool = []
    intermediate_pool = []
    advanced_pool = []

    for ex in all_ex:
        name = ex["name"].lower()
        diff = difficulty_of(ex)

        # --- BEGINNER FILTERS ---
        if is_simple(ex):
            beginner_pool.append(ex)
            continue

        # If user has condition → avoid jumps / impact
        if has_condition and any(k in name for k in ["jump", "box", "burpee", "impact"]):
            continue

        # --- ADVANCED FILTERS ---
        if is_hard(ex) or diff in ["advanced", "expert", "hard"]:
            advanced_pool.append(ex)
            continue

        # --- INTERMEDIATE (everything else) ---
        intermediate_pool.append(ex)

    # Fallback if too small
    if len(beginner_pool) < 10:
        beginner_pool = [ex for ex in all_ex if not is_hard(ex)]

    if len(intermediate_pool) < 10:
        intermediate_pool = all_ex

    if len(advanced_pool) < 10:
        advanced_pool = [ex for ex in all_ex if is_hard(ex)]

    # Shuffle pools
    random.shuffle(beginner_pool)
    random.shuffle(intermediate_pool)
    random.shuffle(advanced_pool)

    beginner = beginner_pool[:10]
    intermediate = intermediate_pool[:10]
    advanced = advanced_pool[:10]

    # Final program
    programs = [
        (beginner, "Beginner Program"),
        (intermediate, "Intermediate Program"),
        (advanced, "Advanced Program"),
    ]

    final_output = []

    for ex_set, label in programs:
        for ex in ex_set:
            name = ex["name"].replace("(equipment)", "").strip()
            level = label.split()[0].lower()
            sets, reps, rest = generate_sets_reps_rest(level, has_condition)

            final_output.append((
                {
                    "name": name,
                    "sets": sets,
                    "reps": reps,
                    "rest": rest
                },
                label
            ))

    return final_output



def generate_sets_reps_rest(level, has_condition=False):
    level = level.lower()

    if level == "beginner":
        sets, reps, rest = 3, 15, 30
    elif level == "intermediate":
        sets, reps, rest = 4, 12, 45
    else:  # advanced
        sets, reps, rest = 5, 10, 60

    # Safety if condition
    if has_condition:
        reps = max(8, int(reps * 0.8))
        sets = max(2, sets - 1)
        rest += 20

    return sets, reps, rest

def difficulty_of(ex):
    return ex.get("difficulty", "").strip().lower()
'''


