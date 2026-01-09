import bcrypt
import mysql.connector
import requests
from mysql.connector import Error
import json
import os

# GOAL NORMALIZATION (GLOBAL)
def normalize_goal(goal):
    if not goal:
        return goal

    goal = str(goal).strip().lower().replace(" ", "_")

    return {
        "gain_muscles": "gain_muscle",
        "gain_muscle": "gain_muscle",
        "lose_weight": "lose_weight",
        "gain_weight": "gain_weight",
        "keep_fit": "keep_fit",
        "maintain": "keep_fit",
        "maintain_weight": "keep_fit",
    }.get(goal, goal)

# Encrypted Password
def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


class AuthTbl:

    def clear_user_saved_exercises(self, user_id):
        """
        Clears all saved/favorited exercises when goals or health condition change
        """
        if not self.db:
            print("❌ Database not connected")
            return False

        try:
            self.cursor.execute(
                """
                DELETE FROM saved_exercises_by_user
                WHERE UserId = %s
                """,
                (user_id,)
            )
            self.db.commit()
            print(f"🧹 Cleared saved exercises for user {user_id}")
            return True

        except Exception as e:
            print("❌ Failed to clear saved exercises:", e)
            self.db.rollback()
            return False

    # Change Password
    def verify_user_password(self, user_id, plain_password):
        if self.db is None:
            return False
        try:
            sql = "SELECT Password FROM data_db WHERE UserId = %s LIMIT 1"
            self.cursor.execute(sql, (user_id,))
            row = self.cursor.fetchone()

            if not row:
                return False

            stored_hash = row["Password"]
            return verify_password(plain_password, stored_hash)

        except Exception as e:
            print("Verify password error:", e)
            return False

    def update_password(self, user_id, new_plain_password):
        if self.db is None:
            return False

        try:
            hashed = hash_password(new_plain_password)

            sql = """
                UPDATE data_db
                SET Password = %s, Updated_at = NOW()
                WHERE UserId = %s
            """
            self.cursor.execute(sql, (hashed, user_id))
            self.db.commit()

            return self.cursor.rowcount > 0

        except Exception as e:
            print("Update password error:", e)
            self.db.rollback()
            return False

    def get_email_by_user_id(self, user_id):
        if self.db is None:
            return None

        try:
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT Email FROM data_db WHERE UserId = %s LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            cursor.close()

            return row[0] if row else None

        except Error as e:
            print("Get email error:", e)
            return None

    def username_exists(self, username):
        sql = "SELECT 1 FROM data_db WHERE Username=%s LIMIT 1"
        self.cursor.execute(sql, (username,))
        return self.cursor.fetchone() is not None

    def check_password(self, username, password):
        sql = """
            SELECT UserId, Password
            FROM data_db
            WHERE Username = %s
            LIMIT 1
        """
        self.cursor.execute(sql, (username,))
        row = self.cursor.fetchone()

        if not row:
            return None

        stored_hash = row["Password"]

        if verify_password(password, stored_hash):
            return row["UserId"]

        return None

    def load_health_conditions(self):
        path = os.path.join(os.path.dirname(__file__), "health_conditions.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)["health_conditions"]

    def username_exists(self, username):
        try:
            sql = "SELECT 1 FROM data_db WHERE Username = %s LIMIT 1"
            self.cursor.execute(sql, (username,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            print("Username exists check error:", e)
            return False

    def get_user_by_id(self, user_id):
        query = """
                SELECT UserId, Fullname, Photo
                FROM data_db
                WHERE UserId = %s \
                """
        self.cursor.execute(query, (user_id,))
        result = self.cursor.fetchone()

        if not result:
            return None

        return {
            "user_id": result["UserId"],
            "fullname": result["Fullname"],
            "photo": result["Photo"],
        }

    def email_exists(self, email):
        try:
            sql = "SELECT 1 FROM data_db WHERE Email = %s LIMIT 1"
            self.cursor.execute(sql, (email,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            print("Email exists check error:", e)
            return False

    def __init__(self):
        try:
            self.db = mysql.connector.connect(
                host="localhost",
                user="root",
                passwd="020820@Steph",
                port=3306,
                database="fitnessgo"
            )
            self.cursor = self.db.cursor(dictionary=True)

            # ✅ LOAD HEALTH CONDITIONS JSON HERE
            self.health_conditions = self.load_health_conditions()

            print("Connected to MySQL successfully!")
        except Error as e:

            self.db = None
            self.cursor = None
            self.health_conditions = {}  # safety fallback

    def is_valid_health_condition(self, condition_key):
        """
        Checks if a health condition exists in health_conditions.json
        """
        if not condition_key:
            return True  # None means "no condition"

        key = condition_key.strip().lower()
        return key in self.health_conditions

    def calculate_daily_calories_by_condition(
            health_conditions_data,
            condition_key,
            gender
    ):
        condition_key = (condition_key or "none").lower()

        condition = health_conditions_data.get(condition_key)

        if not condition:
            condition = health_conditions_data["none"]

        # If condition is female-only (PCOS, pregnancy, etc.)
        if gender not in condition:
            condition = health_conditions_data["none"]

        return condition[gender]

    def get_condition_calories(self, condition_key, gender):
        key = (condition_key or "none").lower()
        condition = self.health_conditions.get(key)

        if not condition:
            condition = self.health_conditions["none"]

        # Handle female-only conditions (pcos, pregnancy, etc.)
        if gender not in condition:
            condition = self.health_conditions["none"]

        return condition[gender]

    def calculate_daily_goal(
            self,
            weight, height, age, gender,
            activity, goal,
            desired_weight=None,  # ✅ ADD (optional)
            health_condition=None
    ):
        weight = float(weight)
        height = float(height)
        age = int(age)
        gender = gender.lower()

        # BMR (Mifflin–St Jeor)
        if gender == "male":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

        # Activity multipliers (UI-safe)
        activity_factor_map = {
            "not very active": 1.2,
            "lightly active": 1.375,
            "active": 1.55,
            "very active": 1.725
        }

        factor = activity_factor_map.get(
            str(activity).strip().lower(),
            1.2
        )

        tdee = bmr * factor

        # -------------------------------------------------
        # ✅ GOAL ADJUSTMENT (NOW USES desired_weight)
        # -------------------------------------------------
        goal_norm = normalize_goal(goal)

        if desired_weight is not None:
            desired_weight = float(desired_weight)
            weight_diff = desired_weight - weight
        else:
            weight_diff = 0

        if goal_norm == "lose_weight":
            # up to ~500 kcal deficit depending on target gap
            tdee -= min(500, abs(weight_diff) * 110)

        elif goal_norm == "gain_weight":
            # up to ~500 kcal surplus depending on target gap
            tdee += min(500, abs(weight_diff) * 110)

        elif goal_norm == "gain_muscle":
            tdee += 300

        elif goal_norm == "keep_fit":
            pass  # no change
        # -------------------------------------------------

        # Health condition override (JSON)
        condition_key = (health_condition or "none").strip().lower()

        # 🔒 KEEP YOUR VALIDATION (UNCHANGED)
        if condition_key not in self.health_conditions:
            raise ValueError(
                f"Invalid health condition: '{health_condition}'. "
                f"Not found in health_conditions.json"
            )

        condition_data = self.health_conditions[condition_key]

        # Handle female-only conditions safely
        condition_calories = condition_data.get(
            gender,
            self.health_conditions["none"][gender]
        )

        # Blend TDEE with medical recommendation
        daily_goal = (tdee + condition_calories) / 2

        # Age-based modifier
        if age >= 65:
            daily_goal *= 0.95
        elif age <= 18:
            daily_goal *= 1.05

        # Safety limits (UNCHANGED)
        daily_goal = max(1200, min(daily_goal, 4500))

        return int(daily_goal)

    def insert_info(
            self, username, email, password, fullname, age, gender, height,
            weight, goal, activity, desired_weight, has_health_condition,
            specific_condition=None, photo_bytes=None, bmi_status=None
    ):
        if self.db is None:
            raise ConnectionError("Database not connected")
        goal = normalize_goal(goal)

        # 🔐 HASH PASSWORD BEFORE SAVING
        hashed_password = hash_password(password)
        if has_health_condition != "Yes":
            specific_condition = None

        height_m = float(height) / 100
        weight = float(weight)
        bmi = round(weight / (height_m * height_m), 2)

        if bmi < 18.5:
            bmi_status = "Underweight"
        elif bmi < 25:
            bmi_status = "Normal"
        elif bmi < 30:
            bmi_status = "Overweight"
        else:
            bmi_status = "Obese"

        daily_goal = self.calculate_daily_goal(
            weight=weight,
            height=height,
            age=age,
            gender=gender,
            activity=activity,
            goal=goal,
            health_condition=specific_condition
        )

        sql = """
            INSERT INTO data_db 
            (Username, Email, Password, Fullname, Age, Gender, Height, Weight,
             ActivityLevel, Goal, DesiredWeight, HasHealthConditions,
             WhatHealthConditions, Photo, BMI, BMIStatus, DailyNetGoal,
             Created_at, Updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    NOW(), NOW())
        """

        values = (
            username,
            email,
            hashed_password,
            fullname,
            age,
            gender,
            height,
            weight,
            activity,
            goal,
            desired_weight,
            has_health_condition,
            specific_condition,
            photo_bytes,
            bmi,
            bmi_status,
            daily_goal
        )

        try:
            self.cursor.execute(sql, values)
            self.db.commit()
            return self.cursor.lastrowid, bmi, bmi_status, daily_goal

        except Error as e:
            self.db.rollback()
            raise

    def update_photo(self, user_id, photo_bytes):
        try:
            sql = "UPDATE data_db SET Photo = %s WHERE UserId = %s"
            self.cursor.execute(sql, (photo_bytes, user_id))
            self.db.commit()
            print("PHOTO SAVED!")
            return True
        except Error as e:
            print("Photo update error:", e)
            return False

    def get_bmi_and_daily_goal(self, user_id):
        try:
            sql = "SELECT BMI, BMIStatus, DailyNetGoal FROM data_db WHERE UserId = %s"
            self.cursor.execute(sql, (user_id,))
            result = self.cursor.fetchone()
            if result:
                return result["BMI"], result["BMIStatus"], result["DailyNetGoal"]
            else:
                return None, None, None
        except Error as e:
            print("Fetch error:", e)
            return None, None, None

    def insert_food(self, user_id, food_name, quantity, meal_category, calories):
        if self.db is None:
            print("Database not connected!")
            return None

        # Convert quantity to int to match schema
        try:
            quantity = int(quantity)
        except ValueError:
            print("Invalid quantity: must be an integer.")
            return None

        sql = """
            INSERT INTO food_db 
            (UserId, FoodName, FoodQuantity, MealCategory, Calories, Created_at, Updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """

        values = (user_id, food_name, quantity, meal_category, calories)

        try:
            self.cursor.execute(sql, values)
            self.db.commit()

            food_id = self.cursor.lastrowid  # auto-generated
            print(f"FOOD INSERTED → FoodId: {food_id}, UserId: {user_id}")

            return food_id

        except Error as e:
            self.db.rollback()
            print("FOOD INSERT ERROR:", e)
            return None

    def get_user_food_entries_by_date(self, user_id, date_str):
        if self.db is None:
            print("Database not connected!")
            return None

        sql = """
            SELECT 
                FoodId,
                FoodName,
                FoodQuantity,
                MealCategory,
                Calories,
                Created_at
            FROM food_db
            WHERE UserId = %s
            AND DATE(Created_at) = %s
            ORDER BY Created_at DESC
        """

        try:
            self.cursor.execute(sql, (user_id, date_str))
            return self.cursor.fetchall()

        except Error as e:
            print("FETCH FOOD BY DATE ERROR:", e)
            return None

    def delete_food_entry_by_id(self, food_id):
        if self.db is None:
            print("Database not connected!")
            return False

        # Only delete entries created today
        sql = """
            DELETE FROM food_db 
            WHERE FoodId = %s 
            AND DATE(Created_at) = CURDATE()
            LIMIT 1
        """

        try:
            self.cursor.execute(sql, (food_id,))
            self.db.commit()

            if self.cursor.rowcount > 0:
                print(f"FOOD LOG DELETED → ID: {food_id}")
                return True
            else:
                print("Cannot delete past food logs.")
                return False

        except Error as e:
            print("DELETE FOOD ERROR:", e)
            self.db.rollback()
            return False

    def update_food_entry_by_id(self, payload):
        sql = """
            UPDATE food_db
            SET FoodName=%s, FoodQuantity=%s, Calories=%s, MealCategory=%s
            WHERE FoodId=%s
        """

        try:
            self.cursor.execute(sql, (
                payload["FoodName"],
                payload["FoodQuantity"],
                payload["Calories"],
                payload["MealCategory"],
                payload["FoodId"]
            ))
            self.db.commit()
            return self.cursor.rowcount > 0

        except Error as e:
            print("UPDATE FOOD ERROR:", e)
            self.db.rollback()
            return False

    def get_user_photo(self, user_id):
        try:
            sql = "SELECT Photo FROM data_db WHERE UserId = %s"
            self.cursor.execute(sql, (user_id,))
            result = self.cursor.fetchone()
            if result:
                return result["Photo"]
            return None
        except Exception as e:
            print("Error fetching photo:", e)
            return None

        # --- ADD THIS NEW FUNCTION ---

    def get_food_calories(self, food_name, grams):
        """Fetch calories using CalorieNinjas API."""
        api_key = "xkFc9jtNjCRrd7sdLRckPA==J9LAgoqCUBOn3xFC"
        url = "https://api.calorieninjas.com/v1/nutrition?query=" + food_name

        headers = {"X-Api-Key": api_key}

        try:
            response = requests.get(url, headers=headers)
            data = response.json()

            if "items" not in data or len(data["items"]) == 0:
                return 0

            per_100g = data["items"][0]["calories"]
            calories = (per_100g / 100) * grams
            return calories

        except Exception as e:
            print("API ERROR:", e)
            return 0

    def get_user_fullname(self, user_id):
        try:
            sql = "SELECT Fullname FROM data_db WHERE UserId = %s LIMIT 1"
            self.cursor.execute(sql, (user_id,))
            result = self.cursor.fetchone()

            if result:
                return result["Fullname"]
            return None
        except Error as e:
            print("Error fetching fullname:", e)
            return None

    def save_user_exercises(self, user_id, exercises, goal, difficulty, mode):
        # Remove old user exercises
        self.cursor.execute(
            "DELETE FROM user_exercises WHERE UserId=%s",
            (user_id,)
        )
        self.db.commit()

        sql = """
            INSERT INTO user_exercises
            (UserId, Name, Goal, Difficulty, Mode,
             Sets, Reps, RestSeconds, Created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        for ex in exercises:
            self.cursor.execute(sql, (
                user_id,
                ex["name"],
                goal,  # ✅ correct
                difficulty,  # ✅ beginner / intermediate / advanced
                mode,  # ✅ normal / condition
                ex.get("sets", 3),
                ex.get("reps", 12),
                ex.get("rest", 30),
            ))

        self.db.commit()

    def get_user_goal(self, user_id):
        if self.db is None:
            print("❌ ERROR: Database not connected!")
            return None

        try:
            sql = """
                SELECT Goal, HasHealthConditions
                FROM data_db
                WHERE UserId = %s
                LIMIT 1
            """
            self.cursor.execute(sql, (user_id,))
            row = self.cursor.fetchone()

            if not row:
                print(f"⚠️ No user found with ID {user_id}")
                return None

            goal_text = row["Goal"] or ""
            condition_text = row["HasHealthConditions"] or ""

            # Convert goal to JSON format → "gain_weight"
            goal_key = goal_text.strip().lower().replace(" ", "_")

            # Convert "Yes"/"No" to boolean
            has_condition = (condition_text == "Yes")

            return {
                "goal": goal_key,
                "condition": has_condition
            }

        except Exception as e:
            print("🔥 get_user_goal() ERROR:", e)
            return None

    # articleeeee!!!!!!!!!!!!!!!!!
    def get_saved_article_id(self, user_id, title):
        sql = """
            SELECT SavedId
            FROM saved_articles_db
            WHERE UserId = %s AND title = %s
            LIMIT 1
        """
        try:
            self.cursor.execute(sql, (user_id, title))
            row = self.cursor.fetchone()
            return row["SavedId"] if row else None
        except Exception as e:
            print("get_saved_article_id ERROR:", e)
            return None

    def remove_saved_article_by_title(self, user_id, title):
        sql = """
            DELETE FROM saved_articles_db
            WHERE UserId = %s AND title = %s
            LIMIT 1
        """
        try:
            self.cursor.execute(sql, (user_id, title))
            self.db.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            self.db.rollback()
            return False

    def add_saved_exercise(self, user_id, ex, program_name, user_exercise_id=None):
        sql = """
            INSERT INTO saved_exercises_by_user
            (UserId, UserExerciseId, name, difficulty, program_name, 
             sets, reps, rest_seconds, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        try:
            self.cursor.execute(sql, (
                user_id,
                user_exercise_id,  # Will be None/NULL if not provided
                ex["name"],
                program_name.replace(" Program", ""),
                program_name,
                ex["sets"],
                ex["reps"],
                ex["rest"]
            ))
            self.db.commit()
            print(f"❤️ SAVED FAVORITE: {ex['name']} (UserExerciseId={user_exercise_id})")
            return True
        except Exception as e:
            print("🔥 ERROR ADDING SAVED EXERCISE:", e)
            self.db.rollback()
            return False

    def remove_saved_exercise(self, user_id, name):
        sql = """
            DELETE FROM saved_exercises_by_user
            WHERE UserId = %s AND name = %s LIMIT 1
        """

        try:
            self.cursor.execute(sql, (user_id, name))
            self.db.commit()
            print("💔 REMOVED:", name)
            return True

        except Exception as e:
            print("🔥 ERROR REMOVING SAVED EXERCISE:", e)
            self.db.rollback()
            return False

    def get_saved_exercises(self, user_id):
        sql = """
            SELECT name, difficulty, program_name, sets, reps, rest_seconds
            FROM saved_exercises_by_user
            WHERE UserId = %s
            ORDER BY created_at DESC
        """
        self.cursor.execute(sql, (user_id,))
        return self.cursor.fetchall()

    def get_user_goal_info(self, user_id):
        sql = """
            SELECT Goal, DesiredWeight, DailyNetGoal
            FROM data_db
            WHERE UserId = %s
            LIMIT 1
        """
        self.cursor.execute(sql, (user_id,))
        return self.cursor.fetchone()

    def get_user_complete_info(self, user_id):
        sql = """
            SELECT Age, Gender, Height, Weight, ActivityLevel, BMI
            FROM data_db
            WHERE UserId = %s
        """
        self.cursor.execute(sql, (user_id,))
        return self.cursor.fetchone()

    def recalculate_daily_goal(self, weight, height, age, gender, activity, goal,
                           desired_weight, has_health_condition=None, specific_condition=None, user_id=None):

        height_m = float(height) / 100  # Convert height from cm to meters
        weight = float(weight)
        bmi = round(weight / (height_m * height_m), 2)  # BMI formula

        # --- Store BMI in the database if user_id is provided ---
        if user_id:
            self.update_user_bmi(user_id, bmi)

        return self.calculate_daily_goal(
            weight=weight,
            height=height,
            age=age,
            gender=gender,
            activity=activity,
            goal=goal,
            desired_weight=desired_weight,  # ✅ REQUIRED
            health_condition=specific_condition
        )

    def update_user_goals(self, user_id, goal, desired_weight, daily_goal):
        sql = """
            UPDATE data_db
            SET Goal=%s, DesiredWeight=%s, DailyNetGoal=%s
            WHERE UserId=%s
        """
        try:
            self.cursor.execute(sql, (goal, desired_weight, daily_goal, user_id))
            self.db.commit()
            return self.cursor.rowcount > 0
        except:
            self.db.rollback()
            return False

    def update_user_bmi(self, user_id, bmi):
        sql = """
            UPDATE data_db
            SET BMI=%s
            WHERE UserId=%s
        """
        self.cursor.execute(sql, (bmi, user_id))
        self.db.commit()

    def get_user_profile_info(self, user_id):
        sql = """
            SELECT Username, Fullname, Age, Gender, Height, Weight,
                   ActivityLevel, HasHealthConditions, WhatHealthConditions
            FROM data_db
            WHERE UserId = %s
            LIMIT 1
        """
        self.cursor.execute(sql, (user_id,))
        return self.cursor.fetchone()

    def update_user_profile(self, user_id, username, fullname, age, gender,
                            height, weight, activity, has_condition, condition):

        # NORMALIZE HEALTH CONDITION
        if has_condition == "No":
            condition = None
        else:
            condition = (condition or "").strip()

            if not condition:
                raise ValueError("Health condition must be specified.")

            key = condition.lower()
            if key not in self.health_conditions:
                raise ValueError(
                    f"Invalid health condition: '{condition}'. "
                    f"Not found in health_conditions.json"
                )

        # GET CURRENT GOAL INFO
        goal_info = self.get_user_goal_info(user_id)
        if not goal_info:
            print("No goal info found for user:", user_id)
            return False

        goal = goal_info["Goal"]
        desired_weight = goal_info["DesiredWeight"]

        # RECALCULATE DAILY GOAL
        new_daily_goal = self.calculate_daily_goal(
            weight=weight,
            height=height,
            age=age,
            gender=gender,
            activity=activity,
            goal=goal,
            health_condition=condition
        )

        # RECALCULATE BMI IF NEEDED
        height_m = float(height) / 100
        weight = float(weight)
        new_bmi = round(weight / (height_m * height_m), 2)

        current_bmi = self.get_user_complete_info(user_id)["BMI"]

        if current_bmi != new_bmi:
            self.update_user_bmi(user_id, new_bmi)

        # UPDATE DATABASE
        sql = """
            UPDATE data_db
            SET Username=%s, Fullname=%s, Age=%s, Gender=%s,
                Height=%s, Weight=%s, ActivityLevel=%s,
                HasHealthConditions=%s, WhatHealthConditions=%s,
                DailyNetGoal=%s,
                Updated_at = NOW()
            WHERE UserId=%s
        """

        try:
            self.cursor.execute(sql, (
                username,
                fullname,
                age,
                gender,
                height,
                weight,
                activity,
                has_condition,
                condition,
                new_daily_goal,
                user_id
            ))
            self.db.commit()
            return self.cursor.rowcount > 0

        except Error as e:
            print("UPDATE PROFILE ERROR:", e)
            self.db.rollback()
            return False

    def delete_user(self, user_id):
        try:
            print("DEBUG: Deleting user_id =", user_id)

            # DELETE CHILD TABLES FIRST (required because of foreign key constraints)
            self.cursor.execute("DELETE FROM food_db WHERE UserId = %s", (user_id,))
            print("DEBUG: Deleted from food_db")

            self.cursor.execute("DELETE FROM saved_activity WHERE UserId = %s", (user_id,))
            print("DEBUG: Deleted from saved_activity")

            self.cursor.execute("DELETE FROM post_db WHERE UserId = %s", (user_id,))
            print("DEBUG: Deleted from post_db")

            # DELETE PARENT TABLE LAST
            self.cursor.execute("DELETE FROM data_db WHERE UserId = %s", (user_id,))
            print("DEBUG: Deleted from data_db")

            # APPLY CHANGES
            self.db.commit()
            print("DEBUG: Commit successful")
            return True

        except Exception as e:
            print("ERROR DURING DELETE:", e)
            self.db.rollback()
            return False

    def is_logged_in(self, user_id):
        if not user_id:
            return False

        try:
            query = "SELECT UserId FROM data_db WHERE UserId = %s"
            self.cursor.execute(query, (user_id,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking login status: {e}")
            return False


    #ARTICLEEEEEE
        # article!!!!!!!!!!!!!!!!!
        # my_connector.py

    def save_article(self, user_id, article):
        if not self.is_logged_in(user_id):
            print("❌ Cannot save article: user not logged in.")
            return False

        try:
            sql = """
                INSERT INTO saved_articles_db
                (UserId, ArticleId, category, title, author, date, body, image, Created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """

            values = (
                user_id,
                article.get("ArticleId"),  # ✅ STORE ID
                article.get("category") or "",
                article.get("title") or "",
                article.get("author") or "",
                article.get("date") or "",
                article.get("body") or "",
                article.get("image") or "",
            )

            self.cursor.execute(sql, values)
            self.db.commit()
            print(f"✅ Article saved for user_id={user_id}, ArticleId={article.get('ArticleId')}")
            return True

        except Error as e:
            print("🔥 SAVE ARTICLE ERROR:", e)
            self.db.rollback()
            return False

    def get_saved_articles(self, user_id):
        try:
            sql = """
                SELECT SavedId, ArticleId, category, title, author, date, body, image
                FROM saved_articles_db
                WHERE UserId = %s
                ORDER BY Created_at DESC
            """
            self.cursor.execute(sql, (user_id,))
            return self.cursor.fetchall()

        except Error as e:
            print("GET SAVED ARTICLES ERROR:", e)
            return []

    def delete_saved_article(self, saved_id):
        try:
            sql = "DELETE FROM saved_articles_db WHERE SavedId = %s LIMIT 1"
            self.cursor.execute(sql, (saved_id,))
            self.db.commit()

            return self.cursor.rowcount > 0

        except Error as e:
            print("DELETE ARTICLE ERROR:", e)
            self.db.rollback()
            return False

# ARTICLE!!!!!!!!!!!!!!!!!!!


#ARTICLEEEEEEEEEEEEEEE
    def create_post(self, user_id, text, image_bytes=None, audience="Public"):
        try:
            sql = """
                  INSERT INTO posts_tb (UserId, PostText, PostImage, Audience, Created_at)
                  VALUES (%s, %s, %s, %s, NOW())
                  """
            values = (user_id, text, image_bytes, audience)
            self.cursor.execute(sql, values)
            self.db.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"Create post error: {e}")
            self.db.rollback()
            return None

    def update_post_image(self, post_id, image_bytes):
        try:
            print("IMAGE SIZE:", len(image_bytes))

            sql = """
                  UPDATE posts_tb
                  SET PostImage = %s
                  WHERE PostId = %s
                  """
            self.cursor.execute(sql, (image_bytes, post_id))
            self.db.commit()
            return True

        except Exception as e:
            print("Update post image error:", e)
            return False

    def remove_post_image(self, post_id):
        cursor = self.db.cursor()
        query = """
                UPDATE posts_tb
                SET PostImage = NULL
                WHERE PostId = %s \
                """
        cursor.execute(query, (post_id,))
        self.db.commit()
        cursor.close()
        print(f"✔ Image removed for post {post_id}")

    def get_user_posts(self, user_id):
        try:
            sql = """
                  SELECT p.PostId,
                         p.PostText,
                         p.PostImage,
                         p.Created_at,
                         p.Audience,
                         u.UserId,
                         u.Fullname,
                         u.Username,
                         u.Photo
                  FROM posts_tb p
                           JOIN data_db u ON p.UserId = u.UserId
                  WHERE p.UserId = %s
                  ORDER BY p.Created_at DESC \
                  """
            self.cursor.execute(sql, (user_id,))
            return self.cursor.fetchall()

        except Exception as e:
            print("Get user posts error:", e)
            return []

    def get_user_all_posts(self, user_id):
        sql = """
              SELECT *
              FROM posts_tb
              WHERE UserId = %s
              ORDER BY Created_at DESC
              """
        self.cursor.execute(sql, (user_id,))
        return self.cursor.fetchall()

    def get_post_by_id(self, post_id):
        try:
            sql = """
                  SELECT p.PostId, \
                         p.PostText, \
                         p.PostImage, \
                         p.Created_at,
                         p.Audience,
                         u.UserId, \
                         u.Fullname, \
                         u.Username, \
                         u.Photo
                  FROM posts_tb p
                           JOIN data_db u ON p.UserId = u.UserId
                  WHERE p.PostId = %s \
                  """
            self.cursor.execute(sql, (post_id,))
            result = self.cursor.fetchone()
            return result

        except Exception as e:
            print("Get post error:", e)
            return None

    def get_all_posts(self):
        try:
            sql = """
                  SELECT p.PostId, \
                         p.PostText, \
                         p.PostImage, \
                         p.Created_at, \
                         p.Audience, \
                         u.UserId, \
                         u.Fullname, \
                         u.Username, \
                         u.Photo
                  FROM posts_tb p
                           JOIN data_db u ON p.UserId = u.UserId
                  WHERE p.Audience = 'Public' and u.AccountStatus = 'Active' -- ✔ filter public only
                  ORDER BY p.Created_at DESC LIMIT 20 -- ✔ keep newest 100 \
                  """
            self.cursor.execute(sql)
            return self.cursor.fetchall()

        except Exception as e:
            print("Get all posts error:", e)
            return []

    def update_post_audience(self, post_id, new_audience):
        try:
            sql = "UPDATE posts_tb SET Audience = %s WHERE PostId = %s"
            self.cursor.execute(sql, (new_audience, post_id))
            self.db.commit()
            return True
        except Exception as e:
            print("Update audience error:", e)
            self.db.rollback()
            return False

    def delete_post(self, post_id):
        try:
            sql = "DELETE FROM posts_tb WHERE PostId = %s"
            self.cursor.execute(sql, (post_id,))
            self.db.commit()
            return True
        except Exception as e:
            print("Delete post error:", e)
            self.db.rollback()
            return False

    def update_post_content(self, post_id, new_content):
        try:
            sql = "UPDATE posts_tb SET PostText = %s WHERE PostId = %s"
            values = (new_content, post_id)

            self.cursor.execute(sql, values)
            self.db.commit()

            print(f"✔ Post {post_id} updated in database")
            return True

        except Exception as e:
            print("❌ Update post content error:", e)
            self.db.rollback()
            return False

    def get_posts_by_user(self, user_id):
        return self.get_user_posts(user_id)

    def get_user_id_by_email(self, email):
        query = "SELECT UserId FROM data_db WHERE Email = %s"
        self.cursor.execute(query, (email,))
        result = self.cursor.fetchone()

        if not result:
            return None

        return result["UserId"]


    def get_user_calorie_profile(self, user_id):
        """
        Returns all data required for calorie display and validation.
        Used by AI calorie flow.
        """
        if self.db is None:
            return None

        cursor = None
        try:
            cursor = self.db.cursor(dictionary=True)
            sql = """
                    SELECT 
                        Age,
                        Gender,
                        Height,
                        Weight,
                        ActivityLevel,
                        Goal,
                        HasHealthConditions,
                        WhatHealthConditions,
                        DailyNetGoal
                    FROM data_db
                    WHERE UserId = %s
                    LIMIT 1
                """
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "age": row["Age"],
                "gender": row["Gender"],
                "height": row["Height"],
                "weight": row["Weight"],
                "activity_level": row["ActivityLevel"],
                "goal": row["Goal"],
                "has_condition": row["HasHealthConditions"],
                "condition": row["WhatHealthConditions"],
                "daily_goal": row["DailyNetGoal"]
            }

        except Exception as e:
            print("🔥 get_user_calorie_profile ERROR:", e)
            return None

        finally:
            if cursor:
                cursor.close()
#adminyuka
    def get_active_accounts(self):
        sql = """
              SELECT Fullname, Email, LastLogin
              FROM data_db
              WHERE AccountStatus = 'Active'
              ORDER BY Fullname \
              """
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def get_deactivated_accounts(self):
        query = """
                SELECT UserId, \
                       FullName AS Fullname, \
                       Email, \
                       LastLogin, \
                       DeactivationReason
                FROM data_db
                WHERE AccountStatus = 'Deactivated'
                ORDER BY UserId DESC \
                """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def update_last_login(self, user_id):
        sql = """
              UPDATE data_db
              SET LastLogin = NOW()
              WHERE UserId = %s \
              """
        self.cursor.execute(sql, (user_id,))
        self.db.commit()

    def auto_deactivate_inactive_accounts(self):
        sql = """
              UPDATE data_db
              SET AccountStatus = 'Deactivated'
              WHERE AccountStatus = 'Active'
                AND LastLogin < DATE_SUB(NOW(), INTERVAL 365 DAY) \
              """
        self.cursor.execute(sql)
        self.db.commit()

    def check_login_status(self, username):
        sql = """
              SELECT UserId, AccountStatus
              FROM data_db
              WHERE Username = %s \
              """
        self.cursor.execute(sql, (username,))
        return self.cursor.fetchone()

    def is_account_deactivated(self, user_id):
        sql = "SELECT AccountStatus FROM data_db WHERE UserId = %s"
        self.cursor.execute(sql, (user_id,))
        row = self.cursor.fetchone()
        return row and row["AccountStatus"] == "Deactivated"

    def get_active_feedwall_users_today(self):
        query = """
                SELECT COUNT(DISTINCT p.UserId) AS active_feedwall_users
                FROM posts_tb p
                         JOIN data_db u ON u.UserId = p.UserId
                WHERE u.AccountStatus = 'Active'
                  AND p.Created_at >= CURDATE()
                  AND p.Created_at < CURDATE() + INTERVAL 1 DAY \
                """
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        return row["active_feedwall_users"] if row else 0

    def get_feedwall_users_today(self):
        query = """
                SELECT DISTINCT u.UserId   AS id, \
                                u.FullName AS full_name, \
                                u.Photo    AS photo
                FROM posts_tb p
                         JOIN data_db u ON u.UserId = p.UserId
                WHERE u.AccountStatus = 'Active'
                  AND p.Created_at >= CURDATE()
                  AND p.Created_at < CURDATE() + INTERVAL 1 DAY \
                """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def get_posts_today_by_user(self, user_id):
        query = """
                SELECT p.PostId, \
                       p.UserId, \
                       p.PostText, \
                       p.Audience, \
                       p.PostImage, \
                       p.IsViolated, \
                       p.ViolatedAt, \
\
                       -- 🔥 IMPORTANT: alias   \
                       p.Created_At AS Created_at, \
\
                       u.Fullname   AS Fullname, \
                       u.Photo      AS Photo
                FROM posts_tb p
                         JOIN data_db u ON u.UserId = p.UserId
                WHERE p.UserId = %s
                  AND p.Created_At >= CURDATE()
                  AND p.Created_At < CURDATE() + INTERVAL 1 DAY
                  AND u.AccountStatus = 'Active'
                ORDER BY p.Created_At DESC \
                """
        self.cursor.execute(query, (user_id,))
        return self.cursor.fetchall()

    def get_posts_by_user_and_date(self, user_id, date):
        query = """
                SELECT p.PostId, \
                       p.UserId, \
                       p.PostText, \
                       p.Audience, \
                       p.PostImage, \
                       p.IsViolated, \
                       p.ViolatedAt, \
\
                       p.Created_At AS Created_at, \
\
                       u.Fullname   AS Fullname, \
                       u.Photo      AS Photo
                FROM posts_tb p
                         JOIN data_db u ON u.UserId = p.UserId
                WHERE p.UserId = %s
                  AND DATE (p.Created_At) = %s
                ORDER BY p.Created_At DESC \
                """
        self.cursor.execute(query, (user_id, date))
        return self.cursor.fetchall()


    def add_user_violation(self, user_id):
        query = """
                UPDATE data_db
                SET ViolationCount = ViolationCount + 1
                WHERE UserId = %s \
                """
        self.cursor.execute(query, (user_id,))
        self.db.commit()

    def get_user_violations(self, user_id):
        query = """
                SELECT ViolationCount
                FROM data_db
                WHERE UserId = %s LIMIT 1 \
                """
        self.cursor.execute(query, (user_id,))
        row = self.cursor.fetchone()
        return row["ViolationCount"] if row else 0

    def increment_user_violation(self, user_id):
        query = """
                UPDATE data_db
                SET ViolationCount = COALESCE(ViolationCount, 0) + 1
                WHERE UserId = %s \
                """
        self.cursor.execute(query, (user_id,))
        self.db.commit()

    def get_total_violations(self, user_id):
        query = """
                SELECT ViolationCount
                FROM data_db
                WHERE UserId = %s \
                """
        self.cursor.execute(query, (user_id,))
        row = self.cursor.fetchone()
        return row["ViolationCount"] if row and row["ViolationCount"] else 0

    def get_violator_users(self):
        query = """
                SELECT UserId, \
                       FullName AS Fullname, \
                       Email, \
                       ViolationCount
                FROM data_db
                WHERE AccountStatus = 'Active'
                  AND ViolationCount BETWEEN 1 AND 4
                ORDER BY ViolationCount DESC \
                """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def increment_user_violation(self, user_id):
        try:
            # 1️⃣ Add violation
            self.cursor.execute(
                """
                UPDATE data_db
                SET ViolationCount = ViolationCount + 1
                WHERE UserId = %s
                """,
                (user_id,)
            )

            # 2️⃣ Get updated count
            self.cursor.execute(
                "SELECT ViolationCount FROM data_db WHERE UserId = %s",
                (user_id,)
            )
            row = self.cursor.fetchone()
            violations = row["ViolationCount"] if row else 0

            # 3️⃣ Deactivate ONLY if still active
            if violations >= 5:
                self.cursor.execute(
                    """
                    UPDATE data_db
                    SET AccountStatus      = 'Deactivated',
                        DeactivationReason = 'Due to repeated violations'
                    WHERE UserId = %s
                      AND AccountStatus = 'Active'
                    """,
                    (user_id,)
                )

            self.db.commit()
            return violations

        except Exception as e:
            self.db.rollback()
            print("❌ increment_user_violation error:", e)
            return None

    # auth_tbl.py

    def get_deactivation_reason(self, user_id):
        self.cursor.execute(
            "SELECT DeactivationReason FROM data_db WHERE UserId = %s",
            (user_id,)
        )
        row = self.cursor.fetchone()
        return row["DeactivationReason"] if row else None

    def set_login_notice(self, user_id, message):
        try:
            sql = """
                  UPDATE data_db
                  SET LoginNotice=%s, \
                      ShowLoginNotice=1
                  WHERE UserId = %s \
                  """
            self.cursor.execute(sql, (message, user_id))
            self.db.commit()
            return True
        except Exception as e:
            print("SET LOGIN NOTICE ERROR:", e)
            self.db.rollback()
            return False

    # ============================================
    # ADMIN ARTICLE MANAGEMENT
    # ============================================

    def get_all_articles(self):
        if not self.db:
            print("❌ Database connection not available")
            return []

        try:
            cursor = self.db.cursor(dictionary=True)
            sql = """
                SELECT ArticleId, category, title, author, date, body, image, Created_at
                FROM articles_db
                ORDER BY Created_at DESC
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Error as e:
            print("GET ALL ARTICLES ERROR:", e)
            return []

    def add_article_to_db(self, article_data):
        if not self.db:
            print("❌ Database connection not available")
            return False

        try:
            cursor = self.db.cursor()
            sql = """
                INSERT INTO articles_db
                (category, title, author, date, body, image, Created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """
            values = (
                article_data.get("category", ""),
                article_data.get("title", ""),
                article_data.get("author", ""),
                article_data.get("date", ""),
                article_data.get("body", ""),
                article_data.get("image", "logo.png")
            )
            cursor.execute(sql, values)
            self.db.commit()
            cursor.close()
            print(
                f"✅ Article '{article_data.get('title')}' added successfully")
            return True
        except Error as e:
            print("ADD ARTICLE ERROR:", e)
            self.db.rollback()
            return False

    def delete_article(self, article_id):
        """Delete article from database"""
        if not self.db:
            print("❌ Database connection not available")
            return False

        try:
            cursor = self.db.cursor()
            sql = "DELETE FROM articles_db WHERE ArticleId = %s LIMIT 1"
            cursor.execute(sql, (article_id,))
            self.db.commit()
            cursor.close()
            print(f"✅ Article ID {article_id} deleted successfully")
            return True
        except Exception as e:
            print("DELETE ARTICLE ERROR:", e)
            import traceback
            traceback.print_exc()
            self.db.rollback()
            return False

    def update_article(self, article_id, article_data):
        """Update existing article (optional feature)"""
        if not self.db:
            print("❌ Database connection not available")
            return False

        try:
            cursor = self.db.cursor()
            sql = """
                UPDATE articles_db
                SET category = %s, title = %s, author = %s, 
                    date = %s, body = %s, image = %s
                WHERE ArticleId = %s
                LIMIT 1
            """
            values = (
                article_data.get("category"),
                article_data.get("title"),
                article_data.get("author"),
                article_data.get("date"),
                article_data.get("body"),
                article_data.get("image"),
                article_id
            )
            cursor.execute(sql, values)
            self.db.commit()
            cursor.close()
            print(f"✅ Article ID {article_id} updated successfully")
            return True
        except Exception as e:
            print("UPDATE ARTICLE ERROR:", e)
            import traceback
            traceback.print_exc()
            self.db.rollback()
            return False

    #ai
    def get_or_create_chat(self, user_id):
        if not self.db:
            return None

        try:
            cursor = self.db.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT chat_id 
                FROM ai_chats 
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,)
            )

            chat = cursor.fetchone()
            cursor.close()

            if chat:
                return chat["chat_id"]

            cursor = self.db.cursor()
            cursor.execute(
                """
                INSERT INTO ai_chats (user_id, title, created_at, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (user_id, "AI Fitness Buddy")
            )
            self.db.commit()
            chat_id = cursor.lastrowid
            cursor.close()

            return chat_id

        except Exception as e:
            print("❌ get_or_create_chat error:", e)
            return None

    def save_message(self, chat_id, role, content):
        if not self.db:
            print("❌ Database connection not available")
            return None

        if chat_id is None:
            print("❌ Cannot save message: chat_id is None")
            return None

        try:
            cursor = self.db.cursor()

            cursor.execute(
                """
                INSERT INTO ai_messages (chat_id, role, content, timestamp)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (chat_id, role, content)
            )
            message_id = cursor.lastrowid

            cursor.execute(
                "UPDATE ai_chats SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = %s",
                (chat_id,)
            )

            self.db.commit()
            cursor.close()

            print(f"✅ Saved message {message_id} to chat {chat_id}")
            return message_id

        except Exception as e:
            print(f"❌ Error saving message: {e}")
            import traceback
            traceback.print_exc()
            self.db.rollback()
            return None

    def chat_belongs_to_user(self, chat_id, user_id):
        if not self.db:
            return False

        cursor = self.db.cursor()
        cursor.execute(
            "SELECT 1 FROM ai_chats WHERE chat_id=%s AND user_id=%s",
            (chat_id, user_id)
        )
        result = cursor.fetchone()
        cursor.close()
        return result is not None

    def get_chat_messages(self, chat_id, user_id):
        if not self.db or not chat_id or not user_id:
            return []

        try:
            cursor = self.db.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT m.message_id, m.role, m.content, m.timestamp
                FROM ai_messages m
                JOIN ai_chats c ON m.chat_id = c.chat_id
                WHERE m.chat_id = %s
                  AND c.user_id = %s
                ORDER BY m.timestamp ASC
                """,
                (chat_id, user_id)
            )
            rows = cursor.fetchall() or []
            cursor.close()
            return rows
        except Exception as e:
            print("❌ get_chat_messages error:", e)
            return []

    def delete_message(self, message_id):
        if not self.db:
            print("❌ Database connection not available")
            return False

        try:
            cursor = self.db.cursor()

            cursor.execute(
                "DELETE FROM ai_messages WHERE message_id = %s",
                (message_id,)
            )

            self.db.commit()
            cursor.close()

            print(f"✅ Deleted message {message_id}")
            return True

        except Exception as e:
            print(f"❌ Error deleting message: {e}")
            import traceback
            traceback.print_exc()
            self.db.rollback()
            return False

    def delete_all_messages(self, chat_id):
        if not self.db:
            print("❌ Database connection not available")
            return False

        if chat_id is None:
            print("❌ Cannot delete messages: chat_id is None")
            return False

        try:
            cursor = self.db.cursor()

            cursor.execute(
                "DELETE FROM ai_messages WHERE chat_id = %s",
                (chat_id,)
            )

            self.db.commit()
            cursor.close()

            print(f"✅ Deleted all messages from chat {chat_id}")
            return True

        except Exception as e:
            print(f"❌ Error deleting all messages: {e}")
            import traceback
            traceback.print_exc()
            self.db.rollback()
            return False

    def search_messages(self, chat_id, query):
        if not self.db:
            print("❌ Database connection not available")
            return []

        if chat_id is None:
            print("❌ Cannot search messages: chat_id is None")
            return []

        try:
            cursor = self.db.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT message_id, role, content, timestamp
                FROM ai_messages
                WHERE chat_id = %s AND content LIKE %s
                ORDER BY timestamp ASC
                """,
                (chat_id, f"%{query}%")
            )

            messages = cursor.fetchall() or []
            cursor.close()

            print(f"✅ Found {len(messages)} messages matching '{query}'")
            return messages

        except Exception as e:
            print(f"❌ Error searching messages: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_message_thread_safe(self, chat_id, role, content):
        try:
            # Create a new cursor for this thread
            cursor = self.db.cursor()
            cursor.execute(
                "INSERT INTO ai_messages (chat_id, role, content, timestamp) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)",
                (chat_id, role, content)
            )
            message_id = cursor.lastrowid
            cursor.execute(
                "UPDATE ai_chats SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = %s",
                (chat_id,)
            )
            self.db.commit()
            cursor.close()
            return message_id
        except Exception as e:
            print(f"❌ Error in thread-safe save_message: {e}")
            self.db.rollback()
            return None

    def update_saved_articles_by_article_id(self, article_id, article_data):
        try:
            sql = """
                UPDATE saved_articles_db
                SET
                    category = %s,
                    title    = %s,
                    author   = %s,
                    date     = %s,
                    body     = %s,
                    image    = %s
                WHERE ArticleId = %s
            """

            self.cursor.execute(sql, (
                article_data.get("category", ""),
                article_data.get("title", ""),
                article_data.get("author", ""),
                article_data.get("date", ""),
                article_data.get("body", ""),
                article_data.get("image", ""),
                article_id
            ))

            self.db.commit()
            print(f"🔄 Synced saved articles for ArticleId={article_id}")
            return True

        except Exception as e:
            print("❌ UPDATE SAVED ARTICLES ERROR:", e)
            self.db.rollback()
            return False

    def delete_saved_articles_by_article_id(self, article_id):
        try:
            sql = "DELETE FROM saved_articles_db WHERE ArticleId = %s"
            self.cursor.execute(sql, (article_id,))
            self.db.commit()
            print(f"🗑 Deleted saved articles for ArticleId={article_id}")
            return True
        except Exception as e:
            print("❌ DELETE SAVED ARTICLES ERROR:", e)
            self.db.rollback()
            return False


# Create global instance
auth_tbl = AuthTbl()