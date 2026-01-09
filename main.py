from datetime import datetime, date
from kivy.factory import Factory
from threading import Thread
import mysql.connector
from random import randint
import time
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.core.text import Label as CoreLabel
from threading import Thread
from functools import partial
from kivy.uix.filechooser import FileChooserIconView

from chatbot.chatbot_service import process_message
from kivy.storage.jsonstore import JsonStore
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.screenmanager import FadeTransition
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogIcon, MDDialogSupportingText, \
    MDDialogContentContainer, MDDialogButtonContainer
from kivymd.uix.divider import MDDivider
from kivymd.uix.fitimage import FitImage
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.list import MDListItemHeadlineText, MDListItem, MDListItemSupportingText, MDListItemTertiaryText, \
    MDListItemLeadingIcon, MDListItemLeadingAvatar
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.pickers import MDModalDatePicker, MDModalInputDatePicker
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText
from kivy.properties import BooleanProperty, ListProperty, DictProperty, NumericProperty
from kivy.properties import StringProperty
from PIL import Image as PILImage, ImageOps, ImageDraw
from kivymd.uix.textfield import MDTextField
from plyer import filechooser
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
import io
from exercise_image_map import EXERCISE_IMAGE_MAP
from moderation_utils import has_profanity
from my_connector import auth_tbl
import requests
import json
import os
import re

import os

EXERCISE_PIC_DIR = "exercisepic"

def normalize_goal(goal):
    if not goal:
        return goal

    goal = goal.strip().lower().replace(" ", "_")

    return {
        "gain_muscles": "gain_muscle",
        "gain_muscle": "gain_muscle",
        "lose_weight": "lose_weight",
        "gain_weight": "gain_weight",
        "keep_fit": "keep_fit",
    }.get(goal, goal)

def normalize_exercise_name(name: str) -> str:
    return (
        name.lower()
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


def load_image_blob(image_path):
    if not image_path or not os.path.exists(image_path):
        return None

    with open(image_path, "rb") as f:
        return f.read()


def build_exercise_image_index():
    image_index = {}

    if not os.path.isdir(EXERCISE_PIC_DIR):
        print(f"❌ Image directory not found: {EXERCISE_PIC_DIR}")
        return image_index

    base_dir = os.path.abspath(EXERCISE_PIC_DIR)

    for file in os.listdir(base_dir):
        if not file.lower().endswith((".png", ".jpg", ".jpeg")):
            continue

        name = os.path.splitext(file)[0]
        normalized = normalize_exercise_name(name)

        image_index[normalized] = os.path.join(base_dir, file)

    return image_index

def normalize_exercise_name(name: str) -> str:
    if not name:
        return ""

    name = name.lower().strip()

    # remove left/right variants
    name = re.sub(r"\s*\|\s*(left|right|left\s*&\s*right).*", "", name)

    # normalize hyphens
    name = name.replace("-", " ")

    # normalize plurals
    if name.endswith("s"):
        name = name[:-1]

    return " ".join(word.capitalize() for word in name.split())

def load_image_blob(image_path: str):
    DEFAULT_IMAGE = "exercisepic/profile_default.png"

    final_path = image_path if image_path else DEFAULT_IMAGE

    try:
        with open(final_path, "rb") as f:
            return f.read()
    except Exception:
        # absolute fallback
        with open(DEFAULT_IMAGE, "rb") as f:
            return f.read()

# ---------------------------------------
# NORMALIZE IMAGE MAP KEYS (IMPORTANT)
# ---------------------------------------
NORMALIZED_IMAGE_MAP = {
    normalize_exercise_name(name): path
    for name, path in EXERCISE_IMAGE_MAP.items()
}



FILIPINO_FOODS = {}

def load_filipino_foods():
    global FILIPINO_FOODS
    try:
        path = os.path.join(os.path.dirname(__file__), "filipinofoods.json")
        with open(path, "r", encoding="utf-8") as f:
            FILIPINO_FOODS = json.load(f)
            print("✅ Filipino foods loaded:", len(FILIPINO_FOODS.get("items", [])))
    except Exception as e:
        print("❌ Failed to load filipinofoods.json:", e)
        FILIPINO_FOODS = {"items": []}

load_filipino_foods()

def find_filipino_food(food_name):
    name = food_name.lower().strip()
    for item in FILIPINO_FOODS.get("items", []):
        if item["name"] == name:
            return item
    return None




from exercise_image_map import EXERCISE_IMAGE_MAP

with open("ExerciseDetails.json", "r", encoding="utf-8") as f:
    EXERCISE_DETAILS = json.load(f)["exercises"]

# Load the JSON only once
WORKOUTS_JSON = {}
json_path = os.path.join(os.getcwd(), "Workouts.json")

try:
    with open(json_path, "r", encoding="utf-8") as f:
        WORKOUTS_JSON = json.load(f)
except Exception as e:
    print("⚠️ ERROR LOADING JSON:", e)

def fix_scrollview_glitch(*args):
    for widget in Window.children:
        widget.canvas.ask_update()

Window.bind(on_cursor_leave=lambda *a: Clock.schedule_once(fix_scrollview_glitch, 0))
Window.bind(on_cursor_enter=lambda *a: Clock.schedule_once(fix_scrollview_glitch, 0))
Window.bind(on_focus=lambda *a: Clock.schedule_once(fix_scrollview_glitch, 0))

def auto_generate_program_from_json(goal, has_condition):
    goal_key = goal.lower().replace(" ", "_")

    goal_data = WORKOUTS_JSON.get("goals", {}).get(goal_key)
    if not goal_data:
        print("🔥 ERROR: Goal not found in JSON:", goal_key)
        return []

    programs = []

    # Loop through beginner → intermediate → advanced
    for level_name, level_data in goal_data.items():

        # Pick correct list
        if has_condition == "Yes":
            ex_list = level_data.get("health_condition", [])
        else:
            ex_list = level_data.get("normal", [])

        # Program name for this difficulty
        program_name = f"{goal.title()} {level_name.title()}"

        # Each program should have EXACTLY 10 workouts from JSON
        for ex in ex_list:
            programs.append((
                {
                    "name": ex["name"],
                    "sets": ex["sets"],
                    "reps": ex["reps"],
                    "rest": ex["rest"].replace("s", "")
                },
                program_name  # <= Stored separately per level
            ))

    return programs

def send_otp(email, otp):
    import smtplib
    from email.mime.text import MIMEText

    sender_email = "fitnessgo.noreply@gmail.com"
    app_password = "flpnyemjyunnqdkn"  # Gmail app password

    message = MIMEText(f"Your FitnessGo OTP is: {otp}")
    message["Subject"] = "FitnessGo Verification Code"
    message["From"] = sender_email
    message["To"] = email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, email, message.as_string())
        server.quit()
        print("OTP sent successfully!")
        return True

    except Exception as e:
        print("Email error:", e)
        return False


Window.borderless = True
Window.size = (380, 650)

class ClickableImage(ButtonBehavior, Image):
    pass


class ClickableLabel(ButtonBehavior, MDLabel):
    pass


class WelcomeScreen(MDScreen):
    pass


class ButtonScreen(MDScreen):
    pass



class loginScreen(MDScreen):
    reset_user_id = None
    generated_otp = ""
    otp_created_at = None
    otp_fields = []

    def reset(self):
        self.ids.username_field.text = ""
        self.ids.password_field.text = ""

    def show_msg(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp"
            ),
            duration=2,
            size_hint=(0.9, None),
            height="50dp",
            pos_hint={"center_x": 0.5, "y": 0.02},  # lower position to avoid overlay
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

    def toggle_password_visibility(self, field, icon_btn):
        field.password = not field.password
        icon_btn.icon = "eye" if not field.password else "eye-off"

    def on_pre_enter(self):
        self.ids.username_field.text = ""
        self.ids.password_field.text = ""
        self.ids.password_field.password = True
        self.ids.login_eye_icon.icon = "eye-off"

    def login_user(self):
        username = self.ids.username_field.text.strip()
        password = self.ids.password_field.text.strip()

        if not username or not password:
            self.show_msg("Please enter username and password")
            return

        if not auth_tbl.username_exists(username):
            self.show_msg("Username does not exist.")
            return

        user_id = auth_tbl.check_password(username, password)
        if user_id is None:
            self.show_msg("Incorrect password.")
            return

        auth_tbl.update_last_login(user_id)

        # 🚫 BLOCK DEACTIVATED ACCOUNTS
        if auth_tbl.is_account_deactivated(user_id):
            reason = auth_tbl.get_deactivation_reason(user_id)

            if reason in ("violation", "Due to repeated violations"):
                self.show_msg(
                    "Your account has been deactivated due to violations \nof our rules."
                )
            else:
                self.show_msg(
                    "Your account has been deactivated due to inactivity."
                )
            return

        self.show_msg("Login Successful!")

        fullname = auth_tbl.get_user_fullname(user_id) or username
        app = MDApp.get_running_app()

        app.current_user_id = user_id
        app.current_user_name = fullname
#stay
        app.store.put(
            "user",
            id=user_id,
            name=fullname,
            role="student"
        )

        self.manager.get_screen("dashboard_screen").set_user_id(user_id)
        self.manager.get_screen("exercise_hub").set_user_id(user_id)
        self.manager.get_screen("article_hub").set_user_id(user_id)
        self.manager.get_screen("food_log_screen").set_user_id(user_id)
        self.manager.get_screen("calorie_counter_screen").set_user_id(user_id)

        self.manager.current = "dashboard_screen"

    def open_forgot_password_dialog(self):
        self.generated_otp = ""
        self.otp_fields = []

        if hasattr(self, "timer_event") and self.timer_event:
            self.timer_event.cancel()

        # EMAIL LABEL
        email_label = MDLabel(
            text="Email",
            halign="left",
            size_hint_x=None,
            width=dp(300),
            pos_hint={"center_x": 0.5},
        )

        # EMAIL FIELD
        self.email_field = MDTextField(
            hint_text="Email",
            mode="outlined",
            size_hint_x=None,
            width=dp(300),
            pos_hint={"center_x": 0.5},
            radius=[20, 20, 20, 20],
            theme_line_color="Custom",
            line_color_focus=(0.1, 0.7, 0.1, 1),
        )

        send_otp_btn = MDButton(
            MDButtonText(text="Verify Email"),
            style="text",
            pos_hint={"right": 1},
        )
        send_otp_btn.on_release = self.send_forgot_password_otp

        email_container = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),
            size_hint_y=None,
            height=dp(95),
            size_hint_x=None,
            width=dp(320),
            pos_hint={"center_x": 0.5},
        )
        email_container.add_widget(email_label)
        email_container.add_widget(self.email_field)
        email_container.add_widget(send_otp_btn)

        # OTP LABEL
        otp_label = MDLabel(
            text="Enter the 6-digit code sent to your email",
            halign="center",
            font_size="14sp"
        )

        # OTP BOX
        otp_box = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            size_hint_x=None,
            width=dp(300),
            pos_hint={"center_x": 0.5},
        )

        for _ in range(6):
            tf = MDTextField(
                size_hint=(None, None),
                width=dp(42),
                height=dp(56),
                font_size="22sp",
                halign="center",
                input_filter="int",
                mode="outlined",
                multiline=False,
                radius=[15, 15, 15, 15],
                theme_line_color="Custom",
                line_color_focus=(0.1, 0.7, 0.1, 1),
            )
            tf.bind(text=self.limit_otp_input)
            self.otp_fields.append(tf)
            otp_box.add_widget(tf)

        # RESEND
        self.resend_text = MDButtonText(text="Resend OTP (300s)")
        self.resend_button = MDButton(
            self.resend_text,
            style="text",
            disabled=True,
            pos_hint={"right": 1},
        )
        self.resend_button.on_release = self.resend_forgot_password_otp

        otp_container = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),
            size_hint_y=None,
            height=dp(150),
            size_hint_x=None,
            width=dp(320),
            pos_hint={"center_x": 0.5},
        )
        otp_container.add_widget(otp_label)
        otp_container.add_widget(otp_box)
        otp_container.add_widget(self.resend_button)

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),
            padding=[dp(20), dp(10), dp(20), dp(10)],
            adaptive_height=True,
        )
        content.add_widget(email_container)
        content.add_widget(otp_container)

        cancel_btn = MDButton(
            MDButtonText(text="Cancel"),
            style="filled", theme_bg_color="Custom", md_bg_color=(0.6, 0.8, 0.6, 1),
            on_release=lambda x: self.forgot_pass_dialog.dismiss(),
        )

        verify_btn = MDButton(
            MDButtonText(text="Verify"),
            style="filled", theme_bg_color="Custom", md_bg_color=(0.1, 0.7, 0.1, 1),
            on_release=self.verify_forgot_password_otp,
        )

        self.forgot_pass_dialog = MDDialog(
            MDDialogHeadlineText(text="Forgot Password", halign="center"),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(
                Widget(size_hint_x=1),
                cancel_btn,
                verify_btn,
                spacing="12dp",
            ),
            auto_dismiss=False,
        )
        self.forgot_pass_dialog.open()

    def send_forgot_password_otp(self, *args):
        email = self.email_field.text.strip()

        if not email:
            self.show_msg("Email is required.")
            return

        # ✅ find user by email (need this function sa auth_tbl)
        user_id = auth_tbl.get_user_id_by_email(email)
        if not user_id:
            self.show_msg("Email not registered.")
            return

        self.reset_user_id = user_id

        from time import time
        from random import randint
        self.generated_otp = str(randint(100000, 999999))
        self.otp_created_at = time()

        print("DEBUG OTP:", self.generated_otp)

        if send_otp(email, self.generated_otp):
            self.show_msg("OTP sent successfully.")
            self.start_resend_timer()
        else:
            self.show_msg("Failed to send OTP.")

    def resend_forgot_password_otp(self, *args):
        self.send_forgot_password_otp()

    def verify_forgot_password_otp(self, *args):
        entered = "".join(tf.text.strip() for tf in self.otp_fields)

        if not entered:
            self.show_msg("Please enter the OTP.")
            return

        if len(entered) < 6:
            self.show_msg("Please enter the complete 6-digit OTP.")
            return

        from time import time
        OTP_VALIDITY_SECONDS = 300  # 5 minutes
        if not self.otp_created_at or (time() - self.otp_created_at) > OTP_VALIDITY_SECONDS:
            self.show_msg("Incorrect or expired OTP.")
            return

        if entered != self.generated_otp:
            self.show_msg("Incorrect or expired OTP.")
            return

        # ✅ OTP OK
        self.forgot_pass_dialog.dismiss()
        self.open_forgot_new_password_dialog()

    def password_field_with_eye(self):
        field = MDTextField(
            password=True,
            password_mask="•",
            mode="outlined",
            size_hint_x=1,
            height=dp(48),
            radius=[20, 20, 20, 20],
            theme_line_color="Custom",
            line_color_focus=(0.1, 0.7, 0.1, 1),
        )

        eye_btn = MDIconButton(
            icon="eye-off",
            size_hint=(None, None),
            size=(dp(32), dp(32)),
            pos_hint={"right": 0.92, "center_y": 0.5},
            on_release=lambda x: self.toggle_password_visibility(field, x),
        )

        row = FloatLayout(size_hint_x=None, width=dp(250), height=dp(48))
        field.pos_hint = {"x": 0, "center_y": 0.5}
        row.add_widget(field)
        row.add_widget(eye_btn)
        return field, row

    def open_forgot_new_password_dialog(self):
        self.new_password_field, new_row = self.password_field_with_eye()
        self.confirm_password_field, confirm_row = self.password_field_with_eye()

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=(dp(20), dp(12), dp(20), dp(4)),
            size_hint_y=None,
            height=dp(180),
            size_hint_x=None,
            width=dp(320),
            pos_hint={"center_x": 0.5},
        )

        content.add_widget(MDLabel(text="New Password"))
        content.add_widget(new_row)
        content.add_widget(MDLabel(text="Confirm New Password"))
        content.add_widget(confirm_row)

        cancel_btn = MDButton(
            MDButtonText(text="Cancel"),
            style="filled", theme_bg_color="Custom", md_bg_color=(0.6, 0.8, 0.6, 1),
            on_release=lambda x: self.reset_pass_dialog.dismiss(),
        )

        confirm_btn = MDButton(
            MDButtonText(text="Confirm"),
            style="filled", theme_bg_color="Custom", md_bg_color=(0.1, 0.7, 0.1, 1),
            on_release=self.confirm_forgot_password,
        )

        self.reset_pass_dialog = MDDialog(
            MDDialogHeadlineText(text="Reset Password", halign="center"),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(
                Widget(size_hint_x=1),
                cancel_btn,
                confirm_btn,
                spacing="12dp",
            ),
            auto_dismiss=False,
        )
        self.reset_pass_dialog.open()

    def confirm_forgot_password(self, *args):
        new_pw = self.new_password_field.text.strip()
        confirm_pw = self.confirm_password_field.text.strip()

        if not new_pw or not confirm_pw:
            self.show_msg("All fields are required.")
            return

        if new_pw != confirm_pw:
            self.show_msg("Passwords do not match.")
            return

        if auth_tbl.update_password(self.reset_user_id, new_pw):
            self.reset_pass_dialog.dismiss()
            self.show_msg("Password reset successful!")
        else:
            self.show_msg("Failed to reset password.")

    def limit_otp_input(self, instance, value):
        # force single digit
        if len(value) > 1:
            instance.text = value[-1]

        # auto move to next field
        if value and instance in self.otp_fields:
            idx = self.otp_fields.index(instance)
            if idx < 5:
                self.otp_fields[idx + 1].focus = True

    def start_resend_timer(self):
        if hasattr(self, "timer_event") and self.timer_event:
            self.timer_event.cancel()

        self.resend_seconds = 300
        self.resend_button.disabled = True
        self.resend_text.text = f"Resend OTP ({self.resend_seconds}s)"

        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def update_timer(self, dt):
        self.resend_seconds -= 1
        if self.resend_seconds > 0:
            self.resend_text.text = f"Resend OTP ({self.resend_seconds}s)"
        else:
            self.resend_button.disabled = False
            self.resend_text.text = "Resend OTP"
            self.timer_event.cancel()
    def toggle_password_visibility(self, field, icon_btn):
        field.password = not field.password
        icon_btn.icon = "eye" if not field.password else "eye-off"

    def open_signup(self):
        self.manager.current = "signup_terms_screen"


class SignupTermsScreen(MDScreen):

    TERMS_TEXT = (
        "By using FitnessGo, you agree to:\n\n"
        "1. Conditions of Use\n"
        "By accessing this application, you confirm that you have read, "
        "understood, and agree to comply with these Terms and Conditions.\n\n"
        "2. User Responsibilities\n"
        "You agree to use the system responsibly and only for its intended purpose.\n\n"
        "3. Content and Conduct\n"
        "You must not post harmful or inappropriate content. Content may be reviewed.\n\n"
        "4. Account Management\n"
        "Repeated violations may result in account deactivation.\n\n"
        "5. Data Usage\n"
        "Your data will be used only for system functionality."
    )

    def on_terms_checked(self, checked: bool):
        """
        Enable Accept button only when checkbox is checked
        """
        self.ids.accept_btn.disabled = not checked

    def on_pre_enter(self, *args):
        """
        Reset checkbox and button every time screen is shown
        """
        if "terms_checkbox" in self.ids:
            self.ids.terms_checkbox.active = False

        if "accept_btn" in self.ids:
            self.ids.accept_btn.disabled = True

    def accept_terms(self):
        self.manager.current = "signup_screen"

    def decline_terms(self):
        self.manager.current = "login_screen"

class signupScreen(MDScreen):
    selected_gender = StringProperty("")


    def reset(self):
        self.ids.fullname_field.text = ""
        self.ids.age_field.text = ""
        self.ids.weight_field.text = ""
        self.ids.height_field.text = ""

        self.selected_gender = ""

        for btn in ("female_btn", "male_btn"):
            self.ids[btn].md_bg_color = (0.40, 0.84, 0.40, 1)

    def validate_and_continue(self):
        if self.validate_fields():
            sm_data = self.manager.user_data
            sm_data['fullname'] = self.ids.fullname_field.text.strip()
            sm_data['age'] = int(self.ids.age_field.text.strip())
            sm_data['weight'] = float(self.ids.weight_field.text.strip())
            sm_data['height'] = float(self.ids.height_field.text.strip())
            sm_data['gender'] = self.selected_gender

            self.manager.instant_switch("signup_screen2")

    def validate_fields(self):
        fullname = self.ids.fullname_field.text.strip()
        age = self.ids.age_field.text.strip()
        weight = self.ids.weight_field.text.strip()
        height = self.ids.height_field.text.strip()
        gender = self.selected_gender

        empty_fields = []
        if not fullname: empty_fields.append("Full name")
        if not age: empty_fields.append("Age")
        if not weight: empty_fields.append("Weight")
        if not height: empty_fields.append("Height")
        if not gender: empty_fields.append("Gender")

        if len(empty_fields) > 1:
            self.show_snackbar("Please fill out all fields.")
            return False
        elif len(empty_fields) == 1:
            self.show_snackbar(f"{empty_fields[0]} is required.")
            return False

        if not age.isdigit():
            self.show_snackbar("Age must be a valid integer.")
            return False
        if not self.is_float(weight):
            self.show_snackbar("Weight must be a valid number.")
            return False
        if not self.is_float(height):
            self.show_snackbar("Height must be a valid number.")
            return False

        if int(age) == 0:
            self.show_snackbar("Invalid Age.")
            return False
        if float(weight) == 0:
            self.show_snackbar("Invalid Weight.")
            return False
        if float(height) == 0:
            self.show_snackbar("Invalid Height.")
            return False

        return True

    @staticmethod
    def is_float(value):
        try:
            float(value)
            return True
        except ValueError:
            return False

    def show_snackbar(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text, halign="center", valign="middle",
                theme_text_color="Custom", text_color=(1, 1, 1, 1), font_size="16sp"
            ),
            duration=2, size_hint=(0.9, None), height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.8, 0.1, 0.1, 1), radius=[20, 20, 20, 20],
        )
        snack.open()


class signupScreen2(MDScreen):
    selected_activitylevel = StringProperty("")

    def reset(self):
        self.selected_activitylevel = ""

        for btn in (
                "active_btn",
                "not_active_btn",
                "lightly_active_btn",
                "very_active_btn",
        ):
            self.ids[btn].md_bg_color = (0.40, 0.84, 0.40, 1)

    def validate_and_continue(self):
        if self.validate_fields():
            self.manager.user_data['activity_level'] = self.selected_activitylevel
            self.manager.instant_switch("signup_screen3")

    def validate_fields(self):
        if not self.selected_activitylevel:
            self.show_snackbar("Please select an activity level.")
            return False
        return True

    def show_snackbar(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),  # ← pure white
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.1, 0.1, 0.1, 1),  # Dark background looks cleaner
            radius=[20, 20, 20, 20],
        )
        snack.open()

class signupScreen3(MDScreen):
    selected_goal = StringProperty("")

    def reset(self):
        self.ids.desired_weight_input.text = ""
        self.selected_goal = ""

        for btn in (
                "loss_weight_btn",
                "gain_weight_btn",
                "keep_fit_btn",
                "gain_muscles_btn",
        ):
            self.ids[btn].md_bg_color = (0.40, 0.84, 0.40, 1)

    def validate_and_continue(self):
        desired_weight = self.ids.desired_weight_input.text.strip()

        if not self.selected_goal:
            self.show_snackbar("Please select your goal.")
            return
        if not desired_weight:
            self.show_snackbar("Desired weight is required.")
            return

        try:
            desired_weight_value = float(desired_weight)
            if desired_weight_value <= 0:
                self.show_snackbar("Please enter a valid desired weight.")
                return
        except ValueError:
            self.show_snackbar("Desired weight must be a number.")
            return

        # Retrieve user's current weight from previous screen
        current_weight = float(self.manager.user_data.get('weight', 0))

        # ---- SMART GOAL VALIDATION ----
        goal = self.selected_goal

        goal = self.selected_goal.strip().lower()

        if goal == "lose weight":
            if desired_weight_value >= current_weight:
                self.show_snackbar(
                    f"Must be lower than your current weight ({current_weight} kg)."
                )
                return

        elif goal in ["gain weight", "gain muscles"]:
            if desired_weight_value <= current_weight:
                self.show_snackbar(
                    f"Must be higher than your current weight ({current_weight} kg)."
                )
                return

        elif goal == "keep fit":
            if desired_weight_value != current_weight:
                self.show_snackbar(
                    f"Must be the same as your current weight ({current_weight} kg)."
                )
                return

        # Save data
        sm_data = self.manager.user_data
        sm_data['goal'] = goal
        sm_data['desired_weight'] = desired_weight_value
        self.manager.instant_switch("signup_screen4")

    def show_snackbar(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),  # ← pure white
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.1, 0.1, 0.1, 1),  # Dark background looks cleaner
            radius=[20, 20, 20, 20],
        )
        snack.open()

class signupScreen4(MDScreen):
    selected_healthconditions = ListProperty([])
    show_other_field = BooleanProperty(False)
    selected_boolean_healthcondition = StringProperty("")

    def reset(self):
        self.selected_boolean_healthcondition = ""
        self.selected_healthconditions.clear()
        self.ids.other_condition_input.text = ""
        self.show_other_field = False

        for btn in ("yes_btn", "no_btn"):
            self.ids[btn].md_bg_color = (0.40, 0.84, 0.40, 1)

        for btn in ("heart_disease_btn", "asthma_btn", "others_btn"):
            self.ids[btn].md_bg_color = (0.40, 0.84, 0.40, 1)

    def toggle_condition(self, condition_name, button):
        if condition_name in self.selected_healthconditions:
            self.selected_healthconditions.remove(condition_name)
            button.md_bg_color = (0.40, 0.84, 0.40, 1)
            if condition_name == "Others":
                self.show_other_field = False
        else:
            self.selected_healthconditions.append(condition_name)
            button.md_bg_color = (0, 0.7, 0, 1)
            if condition_name == "Others":
                self.show_other_field = True

    def select_health_condition(self, value):
        self.selected_boolean_healthcondition = value
        if value == "Yes":
            self.show_other_field = True
        else:
            self.show_other_field = False
            self.selected_healthconditions.clear()

    def validate_and_continue(self):
        sm_data = self.manager.user_data

        if self.selected_boolean_healthcondition not in ["Yes", "No"]:
            self.show_snackbar("Please select Yes or No for health conditions.")
            return

        sm_data['has_health_condition'] = self.selected_boolean_healthcondition

        # ✅ NO CONDITION
        if self.selected_boolean_healthcondition == "No":
            self.selected_healthconditions.clear()
            sm_data['specific_condition'] = None
            sm_data['all_conditions'] = []
            self.manager.instant_switch("signup_screen5")
            return

        # ✅ YES CONDITION — must select at least one
        if not self.selected_healthconditions:
            self.show_snackbar("Please select at least one health condition.")
            return

        # Normalize conditions
        conditions = [c.strip().lower() for c in self.selected_healthconditions]

        valid_conditions = auth_tbl.health_conditions.keys()

        # 🔥 HANDLE "OTHERS"
        if "others" in conditions:
            other_text = self.ids.other_condition_input.text.strip().lower()

            if not other_text:
                self.show_snackbar("Please specify your health condition.")
                return

            if other_text not in valid_conditions:
                self.show_snackbar(
                    "This health condition is not supported."
                )
                return

            conditions.remove("others")
            conditions.append(other_text)

        # 🔥 FINAL VALIDATION: every condition must exist in JSON
        for c in conditions:
            if c not in valid_conditions:
                self.show_snackbar(
                    f"'{c.title()}' is not a supported health condition."
                )
                return

        # ✅ STORE DATA
        sm_data['all_conditions'] = conditions
        sm_data['specific_condition'] = conditions[0]  # primary condition

        self.manager.instant_switch("signup_screen5")

    def show_snackbar(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()


class signupScreen5(MDScreen):
    OTP_VALIDITY_SECONDS = 300
    generated_otp = ""
    otp_fields = []

    def reset(self):
        self.ids.username_field.text = ""
        self.ids.email_field.text = ""
        self.ids.password_field.text = ""
        self.ids.con_password_field.text = ""

    def toggle_password_visibility(self, field, icon_btn):
        field.password = not field.password
        icon_btn.icon = "eye" if not field.password else "eye-off"

    def validate_and_create_account(self):
        if not self.validate_fields():
            return

        self.sm_data = self.manager.user_data
        self.sm_data['username'] = self.ids.username_field.text.strip()
        self.sm_data['email'] = self.ids.email_field.text.strip()
        self.sm_data['password'] = self.ids.password_field.text.strip()

        email = self.sm_data['email']

        from time import time

        otp = str(randint(100000, 999999))
        self.generated_otp = otp
        self.otp_created_at = time()  # ✅ FIX: SET TIME HERE
        print("DEBUG OTP:", otp)

        if not send_otp(email, otp):
            self.show_snackbar("Failed to send OTP. Opening dialog anyway.", success=False)

        self.open_otp_dialog()

    def send_otp_email(self, email):
        from time import time

        otp = str(randint(100000, 999999))
        self.generated_otp = otp
        self.otp_created_at = time()  # ✅ reset time
        print("DEBUG RESEND OTP:", otp)

        return send_otp(email, otp)

    def open_otp_dialog(self):
        self.otp_fields = []

        if hasattr(self, "timer_event") and self.timer_event:
            self.timer_event.cancel()

        otp_box = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            adaptive_height=True,
            size_hint_x=None,
            width=dp(300),
            pos_hint={"center_x": 0.5},
        )

        for i in range(6):
            tf = MDTextField(
                size_hint=(None, None),
                width=dp(40),
                height=dp(60),
                font_size="22sp",
                halign="center",
                input_filter="int",
                mode="outlined",
                multiline=False,
                radius=[15, 15, 15, 15],
                line_color_focus=(0, 0.7, 0, 1),
                theme_line_color="Custom",
            )
            tf.bind(text=self.limit_otp_input)
            self.otp_fields.append(tf)
            otp_box.add_widget(tf)

        # ------------ RESEND BUTTON (FIXED) ------------
        self.resend_text = MDButtonText(text="Resend OTP (300s)")
        self.resend_button = MDButton(
            self.resend_text,
            style="text",
            pos_hint={"center_x": 0.5},
            size_hint=(None, None),
            height=dp(40),
            disabled=True  # ⏱ disabled immediately
        )
        self.resend_button.on_release = self.resend_otp

        # ------------ CONTENT WRAPPER ------------
        content_layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=[dp(10), dp(10), dp(10), dp(0)],
            adaptive_height=True
        )

        content_layout.add_widget(otp_box)
        content_layout.add_widget(self.resend_button)

        # ------------ DIALOG ------------
        self.otp_dialog = MDDialog(
            MDDialogHeadlineText(text="Verify Email"),
            MDDialogSupportingText(
                text="Enter the 6-digit code sent to your email."
            ),
            MDDialogContentContainer(content_layout),
            MDDialogButtonContainer(
                Widget(size_hint_x=1),
                MDButton(MDButtonText(text="Cancel"), style="filled", theme_bg_color="Custom", md_bg_color=(0.6, 0.8, 0.6, 1), on_release=lambda x: self.otp_dialog.dismiss()),
                MDButton(MDButtonText(text="Verify"), style="filled", theme_bg_color="Custom", md_bg_color=(0.1, 0.7, 0.1, 1), on_release=self.verify_otp),
                spacing="10dp"
            ),
            auto_dismiss=False
        )

        self.otp_dialog.open()

        # ✅ START COUNTDOWN IMMEDIATELY
        self.start_resend_timer()

    def limit_otp_input(self, instance, value):
        # force single character
        if len(value) > 1:
            instance.text = value[-1]

        # move to next OTP field
        if value and instance in self.otp_fields:
            idx = self.otp_fields.index(instance)
            if idx < 5:
                self.otp_fields[idx + 1].focus = True

    #  MOVE TO NEXT INPUT
    def move_to_next_otp(self, instance, text):
        if text and instance in self.otp_fields:
            idx = self.otp_fields.index(instance)
            if idx < 5:
                self.otp_fields[idx + 1].focus = True

    #  VERIFY ENTERED OTP
    def verify_otp(self, *args):
        entered = "".join(tf.text.strip() for tf in self.otp_fields)

        if not entered:
            self.show_snackbar("Please enter the OTP.", success=False)
            return

        if len(entered) < 6:
            self.show_snackbar("Please enter the complete 6-digit OTP.", success=False)
            return

        from time import time
        if not hasattr(self, "otp_created_at") or \
                (time() - self.otp_created_at) > self.OTP_VALIDITY_SECONDS:
            self.show_snackbar("OTP has expired. Please resend.", success=False)
            return

        if entered != self.generated_otp:
            self.show_snackbar("Incorrect OTP.", success=False)
            return

        self.otp_dialog.dismiss()
        self.finish_signup()

        #  RESEND OTP
    def resend_otp(self, *args):
        email = self.sm_data['email']
        if self.send_otp_email(email):
            self.show_snackbar("OTP resent!", success=True)
        else:
            self.show_snackbar("Failed to resend OTP.", success=False)

        self.start_resend_timer()

        #  RESEND TIMER
    def start_resend_timer(self):
        if hasattr(self, "timer_event") and self.timer_event:
            self.timer_event.cancel()

        self.resend_seconds = 300
        self.resend_button.disabled = True
        self.resend_text.text = f"Resend OTP ({self.resend_seconds}s)"

        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def update_timer(self, dt):
        self.resend_seconds -= 1

        if self.resend_seconds > 0:
            self.resend_text.text = f"Resend OTP ({self.resend_seconds}s)"
        else:
            self.resend_button.disabled = False
            self.resend_text.text = "Resend OTP"
            if hasattr(self, "timer_event"):
                self.timer_event.cancel()

    def finish_signup(self):
        try:
            sm_data = self.sm_data
            has_health_condition = sm_data.get('has_health_condition', 'No')

            raw_goal = sm_data.get('goal', 'Maintain')
            normalized_goal = normalize_goal(raw_goal)  # ✅ FIX

            user_id, bmi, bmi_status, daily_goal = auth_tbl.insert_info(
                username=sm_data.get('username', 'N/A'),
                email=sm_data.get('email', 'N/A'),
                password=sm_data.get('password', 'N/A'),
                fullname=sm_data.get('fullname', 'N/A'),
                age=sm_data.get('age', 0),
                gender=sm_data.get('gender', 'N/A'),
                height=sm_data.get('height', 0.0),
                weight=sm_data.get('weight', 0.0),
                goal=normalized_goal,  # ✅ ALWAYS normalized
                activity=sm_data.get('activity_level', 'Low'),
                desired_weight=sm_data.get('desired_weight', sm_data.get('weight', 0.0)),
                has_health_condition=has_health_condition,
                specific_condition=sm_data.get('specific_condition', None),
                photo_bytes=sm_data.get('photo_bytes', None),
                bmi_status=None
            )

            # ✅ SUCCESS PATH
            self.manager.created_user_id = user_id
            self.show_snackbar("Account created successfully!", success=True)

            app = MDApp.get_running_app()
            app.current_user_name = sm_data.get('fullname', 'User')
            app.current_user_id = user_id
            self.manager.user_data = {}
            self.manager.instant_switch("signup_screen6")

        except mysql.connector.errors.IntegrityError:
            self.show_snackbar("This email is already registered.", success=False)

        except Exception as e:
            print("ERROR CREATING ACCOUNT:", e)
            self.show_snackbar("Failed to create account", success=False)
    def validate_fields(self):
        username = self.ids.username_field.text.strip()
        email = self.ids.email_field.text.strip()
        password = self.ids.password_field.text.strip()
        con_password = self.ids.con_password_field.text.strip()

        empty_fields = []
        if not username: empty_fields.append("Username")
        if not email: empty_fields.append("Email")
        if not password: empty_fields.append("Password")
        if not con_password: empty_fields.append("Confirm Password")

        if len(empty_fields) > 1:
            self.show_snackbar("Please fill out all fields.", success=False)
            return False
        if len(empty_fields) == 1:
            self.show_snackbar(f"{empty_fields[0]} is required.", success=False)
            return False

        if not email.endswith("@iskolarngbayan.pup.edu.ph"):
            self.show_snackbar("Email must be a valid PUP student email.", success=False)
            return False

        # 🔥 SEPARATED VALIDATION
        username_taken = auth_tbl.username_exists(username)
        email_taken = auth_tbl.email_exists(email)

        if username_taken and email_taken:
            self.show_snackbar("Username and email already exist.", success=False)
            return False

        if username_taken:
            self.show_snackbar("Username is already taken.", success=False)
            return False

        if email_taken:
            self.show_snackbar("Email is already registered.", success=False)
            return False

        if len(password) < 6:
            self.show_snackbar("Password must be at least 6 characters.", success=False)
            return False

        if password != con_password:
            self.show_snackbar("Passwords do not match.", success=False)
            return False

        return True
    def on_pre_enter(self):

        self.ids.password_field.password = True
        self.ids.con_password_field.password = True
        self.ids.password_eye_icon.icon = "eye-off"
        self.ids.confirm_password_eye_icon.icon = "eye-off"

    def show_snackbar(self, text, success=True):

        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

class signupScreen6(MDScreen):
    selected_image_path = StringProperty("")
    photo_bytes = None
    user_id = None

    def reset(self):
        if "profile_img" in self.ids:
            self.ids.profile_img.texture = None
            self.ids.profile_img.source = "profile_default.png"
            self.ids.profile_img.reload()

        self.selected_image_path = ""
        self.photo_bytes = None
        self.user_id = None

    def on_pre_enter(self, *args):
        uid = getattr(self.manager, "created_user_id", None)

        if isinstance(uid, tuple):
            self.user_id = uid[0]
        else:
            self.user_id = uid

        if not self.user_id:
            self.show_snackbar("ERROR: User ID missing!", success=False)

    def make_image_circle(self, path):
        img = PILImage.open(path).convert("RGBA")
        size = min(img.size)
        img = ImageOps.fit(img, (size, size))

        mask = PILImage.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def open_file_manager(self):
        filechooser.open_file(on_selection=self.on_file_select)

    def on_file_select(self, selection):
        if not selection:
            return

        path = selection[0]
        ext = os.path.splitext(path)[1].lower()

        # ❌ BLOCK VIDEOS
        if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"):
            self.show_snackbar("Videos are not allowed. Please select an image.", success=False)
            return

        # ❌ BLOCK NON-IMAGE FILES
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            self.show_snackbar("Invalid file type. Please select an image.", success=False)
            return

        # ✅ IMAGE IS VALID
        self.selected_image_path = path

        try:
            buffer = self.make_image_circle(path)
            self.ids.profile_img.texture = CoreImage(buffer, ext="png").texture
            self.photo_bytes = buffer.getvalue()

            self.show_snackbar("Profile picture selected!", success=True)

        except Exception as e:
            print("Image processing error:", e)
            self.show_snackbar("Failed to load image.", success=False)

    def save_profile_photo(self):
        if not self.photo_bytes:
            self.show_snackbar("Please select a photo first.", success=False)
            return

        if not self.user_id:
            self.show_snackbar("User ID missing!", success=False)
            return

        success = auth_tbl.update_photo(self.user_id, self.photo_bytes)

        if success:
            self.show_snackbar("Photo saved successfully!", success=True)
            next_screen = self.manager.get_screen("signup_screen7")
            next_screen.set_user_id(self.user_id)
            self.manager.instant_switch("signup_screen7")
        else:
            self.show_snackbar("Failed to upload photo.", success=False)

    def skip_photo(self):
        if not self.user_id:
            self.show_snackbar("User ID missing!", success=False)
            return

        next_screen = self.manager.get_screen("signup_screen7")
        next_screen.set_user_id(self.user_id)
        self.manager.instant_switch("signup_screen7")

    def show_snackbar(self, text, success=True):

        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

class SignupScreen7(MDScreen):
    user_id = None  # will be set by previous screen

    def reset(self):
        self.user_id = None
        self._data_loaded = False

        self.ids.dailycaloriegoal_message.text = ""
        self.ids.bmi_message.text = ""
        self.ids.bmi_status.text = ""

    def set_user_id(self, user_id):
        self.user_id = user_id
        self._data_loaded = False

    def on_pre_enter(self, *args):
        if self.user_id is not None:
            self.load_bmi_and_goal()
        else:
            self.ids.dailycaloriegoal_message.text = "No user ID"
            self.ids.bmi_message.text = "No user ID"
            self.ids.bmi_status.text = "User not detected"

    def load_bmi_and_goal(self):
        if hasattr(self, '_data_loaded') and self._data_loaded:
            return  # Skip if data already loaded

        try:
            bmi, bmi_status, daily_goal = auth_tbl.get_bmi_and_daily_goal(self.user_id)
            if bmi is None or daily_goal is None or bmi_status is None:
                self.ids.dailycaloriegoal_message.text = "N/A"
                self.ids.bmi_message.text = "N/A"
                self.ids.bmi_status.text = "Error loading data"
                return

            self.ids.dailycaloriegoal_message.text = f"{daily_goal} Calories"
            self.ids.bmi_message.text = str(bmi)
            self.ids.bmi_status.text = bmi_status  # Use fetched status
            self._data_loaded = True

        except Exception as e:
            self.ids.dailycaloriegoal_message.text = "Error"
            self.ids.bmi_message.text = "Error"
            self.ids.bmi_status.text = f"Error: {str(e)}"

    def go_to_dashboard(self):
        dashboard = self.manager.get_screen("dashboard_screen")
        dashboard.set_user_id(self.user_id)

        exercise_hub = self.manager.get_screen("exercise_hub")
        exercise_hub.set_user_id(self.user_id)

        self.manager.transition.direction = "fade"
        self.manager.instant_switch("dashboard_screen")

    def show_snackbar(self, text, success=True):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

class dashboardScreen(MDScreen):
    user_id = None

    def reset(self):
        self.user_id = None

        self.ids.top_profile_img.texture = None
        self.ids.top_profile_img.source = "profile_default.png"
        self.ids.top_profile_img.reload()

        self.ids.post_profile_img.texture = None
        self.ids.post_profile_img.source = "profile_default.png"
        self.ids.post_profile_img.reload()

    # profile to viewpost
    def go_to_view_post_screen(self):
        if not self.user_id:
            print("❌ Dashboard has no user_id")
            return

        screen = self.manager.get_screen("view_post_screen")
        screen.user_id = self.user_id
        screen.origin = "profile"

        self.manager.transition.direction = "left"
        self.manager.current = "view_post_screen"

    def open_create_post(self):
        app = MDApp.get_running_app()

        self.user_id = self.user_id or app.current_user_id

        if not self.user_id:
            print("❌ Dashboard has no user_id")
            return

        screen = self.manager.get_screen("create_post_screen")
        screen.set_user_id(self.user_id)
        screen.origin = "createpost"

        self.manager.transition.direction = "fade"
        self.manager.current = "create_post_screen"

    def on_pre_enter(self):
        app = MDApp.get_running_app()

        if not self.user_id:
            self.user_id = app.current_user_id

        if not self.user_id:
            print("❌ Dashboard entered without user_id")
            return

        Clock.schedule_once(self.update_feed_height, 0)
        self.load_profile_picture()
        Clock.schedule_once(self.load_feed, 0.2)

        # 🔴 SHOW LOGIN NOTIFICATION (THIS WAS MISSING)
        Clock.schedule_once(lambda dt: self.show_login_notice(), 0.3)

    def update_feed_height(self, dt):
        pass

    def on_profile_image_click(self):
        print("Profile image clicked!")

    def load_profile_picture(self):
        fullname = "User"

        try:
            photo_bytes = auth_tbl.get_user_photo(self.user_id)

            if photo_bytes:
                buffer = io.BytesIO(photo_bytes)
                texture = CoreImage(buffer, ext="png").texture

                # TOP-RIGHT PROFILE ICON
                self.ids.top_profile_img.texture = None
                self.ids.top_profile_img.source = ""
                self.ids.top_profile_img.texture = texture

                # POSTING BOX PROFILE IMAGE
                self.ids.post_profile_img.texture = None
                self.ids.post_profile_img.source = ""
                self.ids.post_profile_img.texture = texture

            else:
                # 🔥 THIS IS THE FIX
                self.ids.top_profile_img.texture = None
                self.ids.top_profile_img.source = "profile_default.png"
                self.ids.top_profile_img.reload()

                self.ids.post_profile_img.texture = None
                self.ids.post_profile_img.source = "profile_default.png"
                self.ids.post_profile_img.reload()

        except Exception as e:
            print("Profile loading error:", e)

            # FAILSAFE RESET
            self.ids.top_profile_img.texture = None
            self.ids.top_profile_img.source = "profile_default.png"
            self.ids.post_profile_img.texture = None
            self.ids.post_profile_img.source = "profile_default.png"

        # LOAD NAME
        try:
            result = auth_tbl.get_user_fullname(self.user_id)
            if result:
                fullname = result
        except Exception as e:
            print("Error getting name:", e)

        self.ids.greeting_label.text = f"Hi, {fullname}!"

        from datetime import datetime
        self.ids.date_label.text = datetime.now().strftime("%A, %B %d")

        self.load_calories()

    def add_post(self, text, image_path=""):
        feed = self.ids.feed_box

        card = MDCard(
            radius=20,
            padding=15,
            size_hint_y=None,
            height="300dp" if image_path else "120dp",
            elevation=3,
        )

        layout = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            size_hint_y=None,
            height=300 if image_path else 120
        )

        layout.add_widget(MDLabel(
            text=f"[b]{self.ids.greeting_label.text.replace('Hi, ', '').replace('!', '')} posted[/b]\n{text}",
            markup=True,
            theme_text_color="Custom",
            text_color=(0, 0, 0, 1),
        ))

        if image_path:
            layout.add_widget(Image(
                source=image_path,
                size_hint_y=None,
                height=200
            ))

        card.add_widget(layout)
        feed.add_widget(card, index=0)

    def load_feed(self, *args):
        posts = auth_tbl.get_all_posts()

        feed = self.ids.feed_box
        feed.clear_widgets()

        for post in posts:
            card = self.build_dashboard_post(post)
            feed.add_widget(card)

    def build_dashboard_post(self, post):
        from kivy.factory import Factory

        card = Factory.PostTemplate()
        card.post_id = post["PostId"]

        # ------- SHOW MENU ONLY IF POST OWNER = CURRENT USER -------
        app = MDApp.get_running_app()
        current_user = app.current_user_id
        post_owner = post["UserId"]

        if current_user == post_owner:
            card.ids.p_menu_button.opacity = 1
            card.ids.p_menu_button.disabled = False
        else:
            card.ids.p_menu_button.opacity = 0
            card.ids.p_menu_button.disabled = True

        # Username
        card.ids.p_username.text = post["Fullname"]

        if post["Audience"] == "Public":
            card.ids.p_audience_icon.icon = "earth"
        else:
            card.ids.p_audience_icon.icon = "lock"

        # Time
        dt = post["Created_at"]
        card.ids.p_time.text = self.format_time(dt)

        # Text
        card.ids.p_text.text = post["PostText"] or ""

        # Profile photo
        if post["Photo"]:
            photo_data = io.BytesIO(post["Photo"])
            tex = CoreImage(photo_data, ext="png").texture
            card.ids.p_user_img.texture = tex
        else:
            card.ids.p_user_img.source = "profile_default.png"

        # Post image
        if post["PostImage"]:
            data = io.BytesIO(post["PostImage"])
            img_tex = CoreImage(data, ext="png").texture
            card.ids.p_image.texture = img_tex

            # REMOVE dp(180) – let KV compute the correct height
            card.ids.p_image.height = img_tex.height
        else:
            card.ids.p_image.height = 0

        return card

    def format_time(self, dt):
        from datetime import datetime, timedelta

        now = datetime.now()
        diff = now - dt

        # --- Less than 1 min ---
        if diff < timedelta(minutes=1):
            return "Just now"

        # --- Minutes ---
        if diff < timedelta(hours=1):
            mins = diff.seconds // 60
            return f"{mins}m"

        # --- Hours ---
        if diff < timedelta(days=1):
            hours = diff.seconds // 3600
            return f"{hours}h"

        # --- Yesterday ---
        if diff < timedelta(days=2):
            return "Yesterday"

        # --- Days (< 7 days) ---
        if diff < timedelta(days=7):
            days = diff.days
            return f"{days}d"

        # --- Same year but more than a week ---
        if dt.year == now.year:
            return dt.strftime("%b %d")  # Example: Dec 05

        # --- Previous years ---
        return dt.strftime("%b %d, %Y")  # Example: Dec 05, 2023

    def set_user_id(self, user_id):
        self.user_id = user_id

    def show_login_notice(self):
        try:
            auth_tbl.cursor.execute(
                """
                SELECT LoginNotice
                FROM data_db
                WHERE UserId = %s
                  AND ShowLoginNotice = 1
                """,
                (self.user_id,)
            )
            row = auth_tbl.cursor.fetchone()
            if not row:
                return

            notice = row["LoginNotice"]

            content = MDBoxLayout(
                orientation="vertical",
                padding=(dp(24), dp(24), dp(24), dp(24)),
                adaptive_height=True,
            )

            content.add_widget(
                MDLabel(
                    text=notice,
                    markup=True,
                    halign="center",
                    theme_text_color="Custom",
                    text_color=(1, 0.2, 0.2, 1),  # 🔴 red
                    font_size="18sp",
                    bold=True,
                )
            )

            self.login_notice_dialog = MDDialog(
                MDDialogHeadlineText(text="ACCOUNT NOTICE"),
                MDDialogContentContainer(content),
                auto_dismiss=True,  # ✅ tap anywhere
            )

            # ✅ ONLY clean DB on dismiss
            self.login_notice_dialog.bind(
                on_dismiss=self._dismiss_login_notice_dialog
            )

            self.login_notice_dialog.open()

        except Exception as e:
            print("LOGIN NOTICE ERROR:", e)

    def _dismiss_login_notice_dialog(self, *args):
        self.login_notice_dialog = None

        try:
            auth_tbl.cursor.execute(
                """
                UPDATE data_db
                SET ShowLoginNotice = 0
                WHERE UserId = %s
                """,
                (self.user_id,)
            )
            auth_tbl.db.commit()
        except Exception as e:
            print("CLEAR LOGIN NOTICE ERROR:", e)

    def load_calories(self):
        try:
            # 1) FETCH DAILY GOAL
            query = "SELECT DailyNetGoal FROM data_db WHERE UserId = %s"
            auth_tbl.cursor.execute(query, (self.user_id,))
            result = auth_tbl.cursor.fetchone()

            if not result:
                return

            daily_goal = float(result["DailyNetGoal"])

            # 2) FETCH CONSUMED TODAY
            consumed_query = """
                SELECT SUM(calories) AS total
                FROM food_db
                WHERE UserId = %s AND DATE(Created_at) = CURDATE()
            """
            auth_tbl.cursor.execute(consumed_query, (self.user_id,))
            consumed_result = auth_tbl.cursor.fetchone()

            consumed = float(consumed_result["total"]) if consumed_result["total"] else 0.0

            # 3) CALCULATE REMAINING
            remaining = max(daily_goal - consumed, 0)

            # 4) UPDATE DASHBOARD LABELS
            self.ids.calorie_intake.text = f"Calorie Intake\n{format(round(daily_goal), ',')}"
            self.ids.calorie_left.text = f"Calorie Left\n{format(round(remaining), ',')}"

        except Exception as e:
            print("Error loading calories:", e)

    def go_to_profile(self):
        profile_screen = self.manager.get_screen("profile_screen")
        profile_screen.set_user_id(self.user_id)
        self.manager.current = "profile_screen"

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.receive_user_id(self.user_id)
        self.manager.transition.direction = "fade"
        self.manager.current = "calorie_counter_screen"

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.transition.direction = "fade"
        self.manager.current = "food_log_screen"

    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_create_post(self):
        screen = self.manager.get_screen("create_post_screen")
        screen.set_user_id(self.user_id)
        self.manager.transition.direction = "fade"
        self.manager.current = "create_post_screen"


class NotificationScreen(MDScreen):
    pass

class CreatePostScreen(MDScreen):
    origin = None  # "profile" or "createpost"

    audience_setting = StringProperty("Public")
    selected_image_path = StringProperty("")
    user_id = None

    def on_enter(self, *args):
        Clock.schedule_once(self._reset_screen, 0)

    def reset_form(self):
        self.ids.post_text.text = ""

        self.selected_image_path = ""

        img = self.ids.preview_image
        img.source = ""
        img.texture = None
        img.height = 0

        self.ids.remove_photo_btn.opacity = 0
        self.ids.remove_photo_btn.disabled = True

        self.audience_setting = "Public"
        self.ids.audience_label.text = "Public"

    def _reset_screen(self, dt):
        self.ids.post_text.text = ""

        img = self.ids.preview_image
        img.source = ""
        img.texture = None
        img.height = 0

        self.ids.remove_photo_btn.opacity = 0
        self.ids.remove_photo_btn.disabled = True

        self.audience_setting = "Public"
        self.ids.audience_label.text = "Public"

        self.ids.createpost_scroll.scroll_y = 1

    def go_back(self):
        print("GO_BACK CALLED | origin =", self.origin)

        if self.ids.post_text.text.strip() or self.selected_image_path:
            self.confirm_discard()
        else:
            self.go_back_based_on_origin()

    def go_back_based_on_origin(self):
        self.manager.transition.direction = "right"

        if self.origin == "profile":
            self.manager.current = "view_post_screen"
        else:
            self.manager.current = "dashboard_screen"

    def on_leave(self, *args):
        self.origin = None

    def confirm_discard(self):
        dialog = MDDialog(
            MDDialogHeadlineText(text="Discard post?"),

            MDDialogContentContainer(
                MDBoxLayout(
                    MDLabel(
                        text="Your draft will be lost.",
                        halign="center",
                    ),
                    MDBoxLayout(
                        size_hint_y=None,
                        height=dp(20),
                    ),

                    # ✅ SPACER
                    # MDBoxLayout(size_hint_y=None, height=dp(20)),

                    # ✅ BUTTON ROW (CENTERED, NO OVERLAP)
                    MDBoxLayout(
                        MDButton(
                            MDButtonText(text="Cancel"),
                            style="filled",
                            theme_bg_color="Custom",
                            md_bg_color=(0.6, 0.8, 0.6, 1),  # light green
                            radius=[20, 20, 20, 20],
                            on_release=lambda *a: dialog.dismiss(),
                        ),
                        MDButton(
                            MDButtonText(text="Discard"),
                            style="filled",
                            theme_bg_color="Custom",
                            md_bg_color=(0.1, 0.7, 0.1, 1),  # dark green
                            radius=[20, 20, 20, 20],
                            on_release=lambda *a: self.discard_post_and_go_back(dialog),
                        ),
                        orientation="horizontal",
                        spacing=dp(24),
                        adaptive_width=True,
                        pos_hint={"center_x": 0.5},
                    ),

                    orientation="vertical",
                    adaptive_height=True,
                    padding=(dp(24), dp(2), dp(24), dp(16)),
                    spacing=dp(20),
                )
            ),

            auto_dismiss=False,
        )

        dialog.open()

    def discard_post_and_go_back(self, dialog):
        dialog.dismiss()
        self.go_back_based_on_origin()


    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()

        # ✅ ALWAYS recover user_id
        if not self.user_id:
            self.user_id = app.current_user_id

        if not self.user_id:
            print("❌ CreatePostScreen entered WITHOUT user_id")
            return

        self.load_profile()

        # origin logic
        if self.origin == "profile":
            pass
        elif self.origin == "createpost":
            pass

    def load_profile(self):
        # Load user profile picture
        photo = auth_tbl.get_user_photo(self.user_id)
        if photo:
            buffer = io.BytesIO(photo)
            self.ids.createpost_profile_img.texture = CoreImage(buffer, ext="png").texture
        else:
            self.ids.createpost_profile_img.source = "profile_default.png"

        # Load user name
        fullname = auth_tbl.get_user_fullname(self.user_id)
        if fullname:
            self.ids.createpost_username.text = fullname

    def set_user_id(self, user_id):
        self.user_id = user_id

    def open_audience_menu(self):
        menu_items = [
            {
                "text": "Public",
                "on_release": lambda x="Public": self.set_audience(x)
            },
            {
                "text": "Only Me",
                "on_release": lambda x="Only Me": self.set_audience(x)
            },
        ]

        self.menu = MDDropdownMenu(
            caller=self.ids.audience_label,
            items=menu_items,
            width_mult=3,
        )
        self.menu.open()

    def pick_image(self):
        from plyer import filechooser
        filechooser.open_file(on_selection=self.on_image_selected)

    def on_image_selected(self, selection):
        if not selection:
            return

        path = selection[0].lower()

        allowed = (".png", ".jpg", ".jpeg", ".webp")

        if not path.endswith(allowed):
            self.show_msg("Only PNG, JPG, or WEBP images are allowed.")
            return

        self.selected_image_path = path

        preview = self.ids.preview_image
        preview.source = path
        preview.height = "220dp"

        # show REMOVE button beside photo icon
        self.ids.remove_photo_btn.opacity = 1
        self.ids.remove_photo_btn.disabled = False

    def remove_image(self):
        self.selected_image_path = ""

        img = self.ids.preview_image
        img.source = ""
        img.texture = None
        img.height = 0

        self.ids.remove_photo_btn.opacity = 0
        self.ids.remove_photo_btn.disabled = True

        # 🔥 FORCE RELAYOUT
        Clock.schedule_once(self._force_layout_fix, 0)

    def _force_layout_fix(self, dt):
        scroll = self.ids.createpost_scroll
        container = scroll.children[0]  # MDBoxLayout inside ScrollView

        container.height = container.minimum_height
        scroll.scroll_y = 1  # snap back to top

    def set_audience(self, selection):
        self.audience_setting = selection
        self.ids.audience_label.text = selection
        self.menu.dismiss()

    def show_msg(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="15sp",
                size_hint_y=None,
                height=dp(48),
                text_size=(None, None),
            ),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            size_hint_x=0.9,
            adaptive_height=True,  # ⭐ IMPORTANT
            padding=(dp(16), dp(16)),
            elevation=6,
        )
        snack.open()

    def submit_post(self):
        if not self.user_id:
            print("❌ BLOCKED: submit_post without user_id")
            return

        text = self.ids.post_text.text.strip()
        image_path = self.selected_image_path

        if not text and not image_path:
            return

        if has_profanity(text):
            self.show_msg(
                "Your post violates community guidelines.\n"
                "Please revise your content before posting."
            )
            return

        image_bytes = None
        if image_path:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

        post_id = auth_tbl.create_post(
            self.user_id,
            text,
            image_bytes,
            self.audience_setting
        )

        if not post_id:
            return

        self.reset_form()  # ⭐⭐⭐ THIS LINE FIXES EVERYTHING ⭐⭐⭐

        app = MDApp.get_running_app()
        view_screen = app.root.get_screen("view_post_screen")
        view_screen.set_user_id(self.user_id)
        view_screen.origin = "createpost"

        view_screen.load_post_from_db(post_id)
        view_screen.load_other_posts(self.user_id, post_id)

        self.manager.current = "view_post_screen"

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.receive_user_id(self.user_id)
        self.manager.transition.direction = "fade"
        self.manager.current = "calorie_counter_screen"

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.transition.direction = "fade"
        self.manager.current = "food_log_screen"

    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_stories_hub(self):
        screen = self.manager.get_screen("stories_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("stories_hub")

    def go_to_create_post(self):
        screen = self.manager.get_screen("create_post_screen")
        screen.set_user_id(self.user_id)
        self.manager.transition.direction = "fade"
        self.manager.current = "create_post_screen"

class ViewPostScreen(MDScreen):
    origin = None
    user_id = None

    def open_create_post(self):
        app = MDApp.get_running_app()

        screen = self.manager.get_screen("create_post_screen")
        screen.set_user_id(self.user_id)

        # ✅ THIS IS THE MISSING LINE
        screen.origin = "profile"

        self.manager.transition.direction = "fade"
        self.manager.current = "create_post_screen"

    # ✅ ADD THIS FUNCTION HERE
    def load_posts(self):
        self.ids.post_layout.clear_widgets()
        posts = auth_tbl.get_user_posts(self.user_id)
        self._build_and_add_cards(posts)

    def _build_and_add_cards(self, posts):
        post_layout = self.ids.post_layout

        post_layout.spacing = dp(10)

        for post in posts:
            try:
                card = self.build_post_template(post)

                # ✅ MATCH DASHBOARD SPACING
                card.size_hint_y = None
                card.height = card.minimum_height

                post_layout.add_widget(card)

            except Exception as e:
                print("POST BUILD ERROR:", e)

    def set_user_id(self, user_id):
        self.user_id = user_id

    # UNIVERSAL HEADER LOADER (same for both flows)
    def load_header(self, user_id):
        fullname = auth_tbl.get_user_fullname(user_id)
        if fullname:
            self.ids.header_fullname.text = fullname

        from datetime import datetime
        self.ids.header_date.text = datetime.now().strftime("%A, %B %d")

        photo = auth_tbl.get_user_photo(user_id)
        if photo:
            buffer = io.BytesIO(photo)
            self.ids.header_profile.texture = CoreImage(buffer, ext="png").texture
        else:
            self.ids.header_profile.source = "profile_default.png"

    def load_other_posts(self, user_id, exclude_post_id):
        posts = auth_tbl.get_user_posts(user_id)
        for post in posts:
            if post["PostId"] != exclude_post_id:
                card = self.build_post_template(post)
                self.ids.post_layout.add_widget(card)

    # SCREEN ENTRY
    def on_pre_enter(self, *args):
        app = MDApp.get_running_app()

        # 🔐 HARD GUARANTEE USER ID FIRST
        self.user_id = self.user_id or app.current_user_id
        if not self.user_id:
            print("❌ ViewPostScreen entered without user_id — BLOCKED")
            return

        # ✅ LOAD HEADER
        self.load_header(self.user_id)

        self.load_posts()


    # TOP POST (converted to PostTemplate)
    def load_post_from_db(self, post_id):
        post = auth_tbl.get_post_by_id(post_id)
        if not post:
            print("Post not found")
            return

        # Build PostTemplate card for the TOP POST
        top_card = self.build_post_template(post)

        # Force newly posted to "Just now"
        top_card.ids.p_time.text = "Just now"

        # Insert at top
        post_layout = self.ids.post_layout
        post_layout.clear_widgets()
        post_layout.add_widget(top_card)

        # Mark origin
        self.origin = "createpost"

    # ADD OLDER POSTS UNDER THE TOP POST
    def load_user_posts(self, user_id):
        self.origin = "profile"

        # clear UI FIRST
        post_layout = self.ids.post_layout
        post_layout.clear_widgets()

        # run DB + heavy work in background
        Thread(
            target=self._load_user_posts_thread,
            args=(user_id,),
            daemon=True
        ).start()

    def _load_user_posts_thread(self, user_id):
        posts = auth_tbl.get_user_posts(user_id)

        # send RAW DATA to main thread
        Clock.schedule_once(lambda dt: self._build_and_add_cards(posts))

    def _add_profile_cards(self, cards):
        post_layout = self.ids.post_layout

        # Now add cards to UI
        for card in cards:
            post_layout.add_widget(card)

    def detect_image_ext(self, blob):
        try:
            img = PILImage.open(io.BytesIO(blob))
            return img.format.lower()
        except Exception:
            return None

    # UNIFIED POST TEMPLATE (FOR ALL POSTS)
    def build_post_template(self, post):
        from kivy.factory import Factory
        card = Factory.PostTemplate()
        card.post_id = post["PostId"]

        # ------- SHOW MENU ONLY IF POST OWNER = CURRENT USER -------
        app = MDApp.get_running_app()
        current_user = app.current_user_id
        post_owner = post["UserId"]

        if current_user == post_owner:
            card.ids.p_menu_button.opacity = 1
            card.ids.p_menu_button.disabled = False
        else:
            card.ids.p_menu_button.opacity = 0
            card.ids.p_menu_button.disabled = True

        # Username
        card.ids.p_username.text = post["Fullname"]

        # Time
        dt = post["Created_at"]
        card.ids.p_time.text = self.format_time(dt)

        # Text
        card.ids.p_text.text = post["PostText"] or ""

        if post["Audience"] == "Public":
            card.ids.p_audience_icon.icon = "earth"
        else:
            card.ids.p_audience_icon.icon = "lock"

        # Profile photo
        if post["Photo"]:
            img_bytes = post["Photo"]
            img_type = self.detect_image_ext(img_bytes)

            if img_type:
                img_data = io.BytesIO(img_bytes)
                user_img = CoreImage(img_data, ext=img_type).texture
                card.ids.p_user_img.texture = user_img
            else:
                card.ids.p_user_img.source = "profile_default.png"
        else:
            card.ids.p_user_img.source = "profile_default.png"

        # Post image
        if post["PostImage"]:
            img_bytes = post["PostImage"]
            img_type = self.detect_image_ext(img_bytes)

            if img_type:
                img_data = io.BytesIO(img_bytes)
                img = CoreImage(img_data, ext=img_type).texture
                card.ids.p_image.texture = img
                card.ids.p_image.height = dp(180)
            else:
                card.ids.p_image.height = 0
        else:
            card.ids.p_image.height = 0

        return card  # ⭐⭐⭐ THIS WAS MISSING

    # TIME FORMATTER
    def format_time(self, dt):
        from datetime import datetime, timedelta

        now = datetime.now()
        diff = now - dt

        # --- Less than 1 min ---
        if diff < timedelta(minutes=1):
            return "Just now"

        # --- Minutes ---
        if diff < timedelta(hours=1):
            mins = diff.seconds // 60
            return f"{mins}m"

        # --- Hours ---
        if diff < timedelta(days=1):
            hours = diff.seconds // 3600
            return f"{hours}h"

        # --- Yesterday ---
        if diff < timedelta(days=2):
            return "Yesterday"

        # --- Days (< 7 days) ---
        if diff < timedelta(days=7):
            days = diff.days
            return f"{days}d"

        # --- Same year but more than a week ---
        if dt.year == now.year:
            return dt.strftime("%b %d")  # Example: Dec 05

        # --- Previous years ---
        return dt.strftime("%b %d, %Y")  # Example: Dec 05, 2023


class CalorieCounterScreen(MDScreen):
    menu = None
    user_id = None

    def on_enter(self, *args):
        if self.user_id:
            self.load_daily_calories()

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.current = "food_log_screen"

    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_calorie_counter(self):
        self.manager.current = "calorie_counter_screen"

    def set_user_id(self, user_id):
        self.user_id = user_id

    def receive_user_id(self, user_id):
        self.user_id = user_id

        if hasattr(self, "load_user_data"):
            self.load_user_data(user_id)

    def show_msg(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp"
            ),
            duration=2,
            size_hint=(0.9, None),
            height="50dp",
            pos_hint={"center_x": 0.5, "y": 0.02},
            md_bg_color=(0, 0.6, 0, 1),  # GREEN Snackbar
            radius=[20, 20, 20, 20],
        )
        snack.open()

    def open_meal_dropdown(self, caller_widget):
        if self.menu:
            self.menu.dismiss()
            self.menu = None

        items = [
            {
                "text": item,
                "on_release": lambda x=item, c=caller_widget: self.menu_callback(x, c),
            }
            for item in ["Breakfast", "Lunch", "Snacks", "Dinner"]
        ]

        self.menu = MDDropdownMenu(
            caller=caller_widget,
            items=items,
            width=dp(150),
            position="bottom",
        )
        self.menu.open()

    def menu_callback(self, selected_value, caller_widget):
        caller_widget.text = selected_value
        if self.menu:
            self.menu.dismiss()
            self.menu = None

    def load_daily_calories(self):
        # Fetch daily_goal from DB
        query = "SELECT DailyNetGoal FROM data_db WHERE UserId = %s"
        values = (self.user_id,)
        auth_tbl.cursor.execute(query, values)
        result = auth_tbl.cursor.fetchone()

        daily_goal = float(result["DailyNetGoal"]) if result and result["DailyNetGoal"] else 0.0

        # Fetch total consumed today from DB
        consumed = self.get_today_consumed()

        # Set calorie_intake to the static daily_goal (as per your spec)
        self.ids.calorie_intake.text = f"Calorie Intake\n{format(round(daily_goal), ',')}"

        # Set calorie_left to daily_goal - consumed (dynamic remaining)
        remaining = max(daily_goal - consumed, 0)  # Prevent negative values
        self.ids.calorie_left.text = f"Calorie Left\n{format(round(remaining), ',')}"

    def get_today_consumed(self):
        query = """
            SELECT SUM(calories) AS total
            FROM food_db
            WHERE UserId = %s AND DATE(Created_at) = CURDATE()
        """
        values = (self.user_id,)
        auth_tbl.cursor.execute(query, values)
        result = auth_tbl.cursor.fetchone()
        # Convert to float to match daily_goal's type and avoid Decimal subtraction errors
        return float(result["total"]) if result and result["total"] else 0.0

    def get_calories(self, food_item, food_quantity):
        """Check Filipino JSON first, then CalorieNinjas API."""

        food_item = food_item.lower().strip()

        # ---------- 1️⃣ CHECK FILIPINO JSON FIRST ----------
        filipino_food = find_filipino_food(food_item)

        if filipino_food:
            calories = filipino_food["calories"]
            serving_size = filipino_food.get("serving_size_g", 100)

            calories_per_gram = calories / serving_size
            total = calories_per_gram * food_quantity

            self.ids.foodcalorie.text = f"{round(total, 2)} kcal"
            return

        # ---------- 2️⃣ FALLBACK TO CALORIENINJAS API ----------
        api_key = "xkFc9jtNjCRrd7sdLRckPA==J9LAgoqCUBOn3xFC"
        url = "https://api.calorieninjas.com/v1/nutrition"
        headers = {"X-Api-Key": api_key}
        query_text = f"{food_quantity}g {food_item}"

        try:
            response = requests.get(
                url,
                headers=headers,
                params={"query": query_text},
                timeout=5
            )

            if response.status_code != 200:
                self.ids.foodcalorie.text = "API Error"
                return

            data = response.json()
            items = data.get("items", [])

            if not items:
                self.ids.foodcalorie.text = "Food not found"
                return

            food = items[0]
            calories = food.get("calories")
            serving_size = food.get("serving_size_g", 100)

            if calories is None:
                self.ids.foodcalorie.text = "Food not found"
                return

            calories_per_gram = calories / serving_size
            total = calories_per_gram * food_quantity

            self.ids.foodcalorie.text = f"{round(total, 2)} kcal"

        except Exception as e:
            print("API ERROR:", e)
            self.ids.foodcalorie.text = "Connection error"

    def get_food_calories(self):
        food = self.ids.foodtype.text.strip()
        weight = self.ids.foodweight.text.strip()

        if not food and not weight:
            self.show_msg("Food type and food weight are required!")
            return

        if not food:
            self.show_msg("Food type is required!")
            return

        if not weight:
            self.show_msg("Food weight(g) is required!")
            return

        try:
            grams = float(weight)
        except ValueError:
            self.show_msg("Food Weight must be a number!")
            return

        self.get_calories(food, grams)

    def save_food_entry(self):
        food_name = self.ids.foodtype.text.strip()
        quantity = self.ids.foodweight.text.strip()
        meal_category = self.ids.selectmeal.text.strip()
        calorie_text = self.ids.foodcalorie.text.strip()

        # ---- VALIDATIONS ----
        if not food_name:
            self.show_msg("Food type is required!")
            return

        if not quantity:
            self.show_msg("Food weight is required!")
            return

        if not meal_category:
            self.show_msg("Meal selection is required!")
            return

        if not calorie_text or "kcal" not in calorie_text:
            self.show_msg("Please click GET CALORIES first!")
            return

        # Extract calorie number
        try:
            calories = float(calorie_text.replace("kcal", "").strip())
        except:
            self.show_msg("Invalid calorie format.")
            return

        # GET CURRENT REMAINING CALORIES
        current_left_text = (
            self.ids.calorie_left.text.replace("Calorie Left", "").strip().replace(",", "")
        )

        try:
            current_left = float(current_left_text)
        except:
            current_left = 0

        # NEW FEATURE: PREVENT SAVING IF NOT ENOUGH CALORIES
        if calories > current_left:
            self.show_msg(
                f"Not enough calories left! ({current_left} left, {calories} kcal food)"
            )
            return  # ❌ STOP – DO NOT SAVE FOOD

        # If calories are valid AND user has enough calories, save food
        food_id = auth_tbl.insert_food(
            user_id=self.user_id,
            food_name=food_name,
            quantity=quantity,
            meal_category=meal_category,
            calories=calories
        )

        if not food_id:
            self.show_msg("Error saving food to database!")
            return

        # UPDATE REMAINING CALORIES
        new_left = max(current_left - calories, 0)
        self.ids.calorie_left.text = f"Calorie Left\n{format(round(new_left), ',')}"

        # CLEAR FIELDS
        self.ids.foodtype.text = ""
        self.ids.foodweight.text = ""
        self.ids.selectmeal.text = ""
        self.ids.foodcalorie.text = ""

        self.show_msg("Food entry saved!")

class FoodLogScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_id = None  # Instance variable instead of class
        self.selected_date = None  # Instance variable
        Clock.schedule_once(self.set_initial_date, 0)

    # INITIAL SETUP
    def set_initial_date(self, dt):
        today = datetime.now()
        formatted = today.strftime("%A, %B %d, %Y")
        self.ids.fl_date_btn_text.text = formatted

        self.selected_date = today
        self.load_food_logs()

    def on_enter(self, *args):
        if self.selected_date is None:
            self.selected_date = datetime.now()

        self.load_food_logs()

    def go_to_food_log(self):
        self.manager.current = "food_log_screen"

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.set_user_id(self.user_id)  # 🔥 pass the user id
        self.manager.current = "calorie_counter_screen"

    # DATE PICKERS
    def show_date_picker(self):
        self.temp_selected_date = None
        self.date_dialog = MDModalDatePicker()

        self.date_dialog.bind(
            on_select_day=self.on_select_day,
            on_select_year=self.on_select_year,
            on_ok=self.on_ok,
            on_cancel=self.on_cancel,
            on_edit=self.on_edit
        )

        self.date_dialog.open()

    def on_edit(self, instance_date_picker):
        instance_date_picker.dismiss()
        Clock.schedule_once(self.show_input_picker, 0.2)

    def show_input_picker(self, *args):
        input_dialog = MDModalInputDatePicker()

        input_dialog.bind(
            on_ok=self.on_input_ok,
            on_cancel=self.on_input_cancel
        )

        input_dialog.open()

    def on_input_ok(self, instance_input_picker):
        selected_date = instance_input_picker.get_date()[0]

        self.selected_date = selected_date
        self.ids.fl_date_btn_text.text = selected_date.strftime("%A, %B %d, %Y")
        self.load_food_logs()

        instance_input_picker.dismiss()

    def on_input_cancel(self, instance_input_picker):
        instance_input_picker.dismiss()

    def on_select_day(self, instance_date_picker, selected_day):
        date = instance_date_picker.get_date()[0]

        if self.temp_selected_date:
            self.temp_selected_date = date.replace(
                year=self.temp_selected_date.year
            )
        else:
            self.temp_selected_date = date

    def on_select_year(self, instance_date_picker, selected_year):
        base = instance_date_picker.get_date()[0]
        if self.temp_selected_date:
            self.temp_selected_date = self.temp_selected_date.replace(year=selected_year)
        else:
            self.temp_selected_date = base.replace(year=selected_year)

    def on_ok(self, instance_date_picker):
        if self.temp_selected_date:
            self.selected_date = self.temp_selected_date
            self.ids.fl_date_btn_text.text = self.selected_date.strftime("%A, %B %d, %Y")
            self.load_food_logs()

        instance_date_picker.dismiss()

    def on_cancel(self, instance_date_picker):
        instance_date_picker.dismiss()

    def load_food_logs(self):
        if self.selected_date is None or self.user_id is None:
            return

        date_str = self.selected_date.strftime("%Y-%m-%d")
        is_today = (date_str == datetime.now().strftime("%Y-%m-%d"))

        entries = auth_tbl.get_user_food_entries_by_date(self.user_id, date_str)
        container = self.ids.fl_container
        container.clear_widgets()

        if not entries:
            container.add_widget(
                MDLabel(
                    text="No food logged for this date.",
                    theme_text_color="Custom",
                    text_color=(0.4, 0.4, 0.4, 1),
                    halign="center",
                    size_hint_y=None,
                    height=dp(50),
                )
            )
            return

        for row in entries:
            time_eaten = row["Created_at"].strftime("%I:%M %p")

            # 🔹 LEFT ICON (food)
            icon = MDIconButton(
                icon="food",
                theme_icon_color="Custom",
                icon_color=(0, 0.6, 0, 1),
                size_hint=(None, None),
                size=(dp(36), dp(36)),
                disabled=True,
            )

            # 🔹 TEXT COLUMN
            text_box = MDBoxLayout(
                orientation="vertical",
                spacing=dp(4),
                size_hint_x=1,
            )

            title = MDLabel(
                text=f"{row['FoodName']} • {row['Calories']} kcal",
                bold=True,
                theme_text_color="Primary",
                shorten=True,
                halign="left",
            )

            subtitle = MDLabel(
                text=f"Qty: {row['FoodQuantity']} | Meal: {row['MealCategory']}",
                theme_text_color="Secondary",
                font_size="12sp",
                shorten=True,
                halign="left",
            )

            time_label = MDLabel(
                text=f"Time: {time_eaten}",
                theme_text_color="Secondary",
                font_size="11sp",
                halign="left",
            )

            text_box.add_widget(title)
            text_box.add_widget(subtitle)
            text_box.add_widget(time_label)

            # 🔹 ACTION BUTTONS (RIGHT)
            actions = MDBoxLayout(
                orientation="vertical",
                size_hint_x=None,
                width=dp(48),
                pos_hint={"center_y": 0.5},
            )

            delete_btn = FoodDeleteButton(
                icon="delete",
                style="standard",
                theme_icon_color="Custom",
                icon_color=(0.8, 0.2, 0.2, 1),
                food_item=row,
                food_log_screen=self,
                pos_hint={"center_y": 0.2},
            )

            actions.add_widget(delete_btn)

            # 🔹 ROW LAYOUT (same as Workout)
            row_layout = MDBoxLayout(
                orientation="horizontal",
                spacing=dp(12),
                padding=(dp(12), dp(10), dp(12), dp(10)),
            )

            row_layout.add_widget(icon)
            row_layout.add_widget(text_box)
            row_layout.add_widget(actions)

            # 🔹 CARD CONTAINER (MATCH WORKOUT STYLE)
            card = MDCard(
                row_layout,
                size_hint_y=None,
                height=dp(78),
                radius=[18, 18, 18, 18],
                md_bg_color=(0.95, 0.96, 0.92, 1),
                ripple_behavior=True,
                on_release=lambda x, r=row: self.open_food_update_dialog(r),
            )

            container.add_widget(card)

    def open_food_update_dialog(self, food_row):
        btn = FoodUpdateButton(
            icon="pencil",
            style="standard",
            theme_icon_color="Custom",
            icon_color=(0, 0.6, 0, 1),
            food_item=food_row,
            food_log_screen=self,
        )
        btn.open_update_dialog()

    # SNACKBAR
    def show_snackbar(self, text, success=True):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.1, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

    def set_user_id(self, user_id):
        self.user_id = user_id

    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_dashboard(self):
        screen = self.manager.get_screen("dashboard_screen")
        screen.set_user_id(self.user_id)
        self.manager.current = "dashboard_screen"

    def go_to_article(self):
        screen = self.manager.get_screen("article_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("article_log_screen")

    def go_to_workout(self):
        screen = self.manager.get_screen("workout_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("workout_log_screen")


class FoodDeleteButton(MDIconButton):
    def __init__(self, icon, style, theme_icon_color, icon_color,
                 food_item, food_log_screen, **kwargs):
        super().__init__(**kwargs)
        self.icon = icon
        self.style = style
        self.theme_icon_color = theme_icon_color
        self.icon_color = icon_color
        self.food_item = food_item
        self.food_log_screen = food_log_screen  # to call reload

    def on_release(self):
        self.confirm_delete()

    def confirm_delete(self):
        self.dialog = MDDialog(
            MDDialogIcon(icon="trash"),
            MDDialogHeadlineText(text=f"Are you sure you want to delete '{self.food_item['FoodName']}' ?"),
            MDDialogSupportingText(
                text=f"This will be permanently deleted from your food log."
            ),
            MDDialogContentContainer(
                MDDivider(),
                orientation="vertical"
            ),

            MDDialogButtonContainer(
                Widget(),

                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled", theme_bg_color="Custom", md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.dialog.dismiss()
                ),

                MDButton(
                    MDButtonText(text="Delete"),
                    style="filled", theme_bg_color="Custom",  md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.delete_food()
                ),
                spacing="10"
            ),
            auto_dismiss=False
        )

        self.dialog.open()

    def delete_food(self):
        # call DB delete function
        res = auth_tbl.delete_food_entry_by_id(self.food_item["FoodId"])

        self.dialog.dismiss()

        if res:
            self.food_log_screen.load_food_logs()
            self.food_log_screen.show_snackbar("Food entry deleted successfully!")
        else:
            self.food_log_screen.show_snackbar("Failed to delete food entry.", success=False)

class FoodUpdateButton(MDIconButton):
    def __init__(self, icon, style, theme_icon_color, icon_color,
                 food_item, food_log_screen, **kwargs):
        super().__init__(**kwargs)
        self.icon = icon
        self.style = style
        self.theme_icon_color = theme_icon_color
        self.icon_color = icon_color
        self.food_item = food_item
        self.food_log_screen = food_log_screen

        self._recalc_event = None  # ✅ debounce holder

    def on_release(self):
        self.open_update_dialog()

    # =====================================================
    # 🔁 CALORIE RECALCULATION LOGIC
    # =====================================================

    def recalculate_calories(self):
        food_name = self.name_field.text.strip().lower()
        qty_text = self.qty_field.text.strip()

        if not food_name or not qty_text:
            self.cal_field.text = "0"
            return

        try:
            grams = float(qty_text)
        except ValueError:
            self.cal_field.text = "0"
            return

        # ---------- 1️⃣ CHECK LOCAL FILIPINO JSON ----------
        filipino_food = find_filipino_food(food_name)

        if filipino_food:
            calories = filipino_food["calories"]
            serving_size = filipino_food.get("serving_size_g", 100)

            calories_per_gram = calories / serving_size
            total_calories = calories_per_gram * grams
            self.cal_field.text = str(round(total_calories, 2))
            return

        # ---------- 2️⃣ FALLBACK TO API (DEBOUNCED) ----------
        api_key = "xkFc9jtNjCRrd7sdLRckPA==J9LAgoqCUBOn3xFC"
        url = "https://api.calorieninjas.com/v1/nutrition"
        query_text = f"{grams}g {food_name}"

        try:
            response = requests.get(
                url,
                headers={"X-Api-Key": api_key},
                params={"query": query_text},
                timeout=5
            )
        except Exception:
            self.cal_field.text = "0"
            return

        if response.status_code != 200:
            self.cal_field.text = "0"
            return

        try:
            data = response.json()
            items = data.get("items", [])

            if not items:
                self.cal_field.text = "0"
                return

            food = items[0]
            api_calories = food.get("calories")
            serving_size = food.get("serving_size_g", 100)

            if api_calories is None:
                self.cal_field.text = "0"
                return

            calories_per_gram = api_calories / serving_size
            total_calories = calories_per_gram * grams
            self.cal_field.text = str(round(total_calories, 2))

        except Exception:
            self.cal_field.text = "0"

    # =====================================================
    # ⏱️ DEBOUNCE (FIXES LAG)
    # =====================================================

    def schedule_recalculate(self):
        if self._recalc_event:
            self._recalc_event.cancel()

        self._recalc_event = Clock.schedule_once(
            lambda dt: self.recalculate_calories(), 0.4
        )

    def on_qty_unfocus(self, instance, focus):
        if not focus:
            self.recalculate_calories()

    def on_name_unfocus(self, instance, focus):
        if not focus:
            self.recalculate_calories()

    # =====================================================
    # 🧾 UPDATE DIALOG
    # =====================================================

    def open_update_dialog(self):
        original_name = self.food_item["FoodName"]
        original_qty = float(self.food_item["FoodQuantity"])
        original_cal = float(self.food_item["Calories"])
        meal_type = self.food_item["MealCategory"]

        self.name_field = MDTextField(
            text=original_name,
            hint_text="Food Name"
        )

        self.qty_field = MDTextField(
            text=str(original_qty),
            hint_text="Quantity (grams)",
            input_filter="float"
        )

        self.cal_field = MDTextField(
            text=str(original_cal),
            hint_text="Calories",
            readonly=True,
            disabled=True
        )

        self.meal_field = MDTextField(
            text=meal_type,
            hint_text="Meal Category",
            readonly=True
        )

        # ✅ LIVE + DEBOUNCED recalculation
        self.qty_field.bind(text=lambda *a: self.schedule_recalculate())
        self.name_field.bind(text=lambda *a: self.schedule_recalculate())

        # ✅ Immediate recalc when leaving field
        self.qty_field.bind(focus=self.on_qty_unfocus)
        self.name_field.bind(focus=self.on_name_unfocus)

        self.meal_field.bind(on_touch_down=self.open_meal_menu)

        self.dialog = MDDialog(
            MDDialogIcon(icon="pencil"),
            MDDialogHeadlineText(text="Update Food Entry"),

            MDDialogContentContainer(
                MDLabel(text="Food Name", bold=True),
                self.name_field,
                MDLabel(text="Food Quantity", bold=True),
                self.qty_field,
                MDLabel(text="Food Calories", bold=True),
                self.cal_field,
                MDLabel(text="Meal Type", bold=True),
                self.meal_field,
                orientation="vertical",
                spacing="15dp",
                padding="10dp",
            ),

            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.dialog.dismiss()
                ),
                MDButton(
                    MDButtonText(text="Update"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.update_food()
                ),
                spacing="10"
            ),
            auto_dismiss=False
        )

        self.dialog.open()

    # =====================================================
    # 🍽️ MEAL MENU
    # =====================================================

    def show_meal_menu(self):
        items = ["Breakfast", "Lunch", "Snacks", "Dinner"]

        self.meal_menu = MDDropdownMenu(
            caller=self.meal_field,
            items=[
                {"text": i, "on_release": lambda x=i: self.meal_selected(x)}
                for i in items
            ],
            width_mult=3
        )
        self.meal_menu.open()

    def meal_selected(self, choice):
        self.meal_field.text = choice
        self.meal_menu.dismiss()

    def open_meal_menu(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.show_meal_menu()

    # =====================================================
    # 💾 SAVE UPDATE
    # =====================================================

    def update_food(self):
        new_name = self.name_field.text.strip()
        new_qty = self.qty_field.text.strip()
        new_cat = self.meal_field.text.strip()
        new_cal = float(self.cal_field.text or 0)

        if not new_name or not new_qty:
            return

        payload = {
            "FoodId": self.food_item["FoodId"],
            "FoodName": new_name,
            "FoodQuantity": float(new_qty),
            "Calories": new_cal,
            "MealCategory": new_cat
        }

        success = auth_tbl.update_food_entry_by_id(payload)

        self.dialog.dismiss()

        if success:
            self.food_log_screen.load_food_logs()
            self.food_log_screen.show_snackbar("Food entry updated successfully!")
        else:
            self.food_log_screen.show_snackbar(
                "Failed to update food entry.", success=False
            )

class WorkoutLogScreen(MDScreen):
    user_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prev_saved_count = None
        self._user_deleted = False

    def open_exercise_detail(self, exercise_name):
        screen = self.manager.get_screen("exercise_detail_screen")
        screen.user_id = self.user_id
        screen.source_screen = "workout_log_screen"  # ✅ ADD

        exercise = {
            "name": exercise_name
        }

        screen.set_exercise(exercise)

        self.manager.transition.direction = "left"
        self.manager.current = "exercise_detail_screen"

    def on_pre_enter(self, *args):
        if self.user_id:
            self.load_saved_exercises()

    def load_saved_exercises(self):
        container = self.ids.fl_container
        container.clear_widgets()

        rows = auth_tbl.get_saved_exercises(self.user_id)
        current_count = len(rows)

        # ================= ADMIN DELETE DETECTION =================
        if (
                self._prev_saved_count is not None
                and not self._user_deleted
                and current_count < self._prev_saved_count
        ):
            self.show_admin_deleted_exercise_notice()
        # ==========================================================

        if not rows:
            container.add_widget(
                MDLabel(
                    text="No saved workouts yet.",
                    theme_text_color="Custom",
                    text_color=(0.4, 0.4, 0.4, 1),
                    halign="center",
                    size_hint_y=None,
                    height=dp(50),
                )
            )
            self._prev_saved_count = current_count
            self._user_deleted = False
            return

        for ex in rows:
            img_path = self.get_exercise_image_path(ex["name"])

            thumb = FitImage(
                source=img_path,
                size_hint=(None, None),
                size=(dp(56), dp(56)),
                radius=[12, 12, 12, 12],
            )

            title = MDLabel(text=ex["name"], bold=True)
            subtitle = MDLabel(
                text=f"{ex['reps']} Reps × {ex['sets']} Sets  Rest: {ex['rest_seconds']}s",
                theme_text_color="Secondary",
                font_size="12sp",
            )

            text_box = MDBoxLayout(orientation="vertical")
            text_box.add_widget(title)
            text_box.add_widget(subtitle)

            delete_btn = MDIconButton(
                icon="delete",
                theme_icon_color="Custom",
                icon_color=(1, 0, 0, 1),
                on_release=lambda x, name=ex["name"]: self.confirm_delete_exercise(name),
            )

            row = MDBoxLayout(
                orientation="horizontal",
                spacing=dp(12),
                padding=(dp(12), dp(10), dp(12), dp(10)),
            )

            row.add_widget(thumb)
            row.add_widget(text_box)
            row.add_widget(delete_btn)

            card = MDCard(
                row,
                size_hint_y=None,
                height=dp(78),
                radius=[18, 18, 18, 18],
                md_bg_color=(0.95, 0.96, 0.92, 1),
                ripple_behavior=True,
                on_release=lambda x, name=ex["name"]: self.open_exercise_detail(name),
            )

            container.add_widget(card)

        # 🔑 SAVE STATE
        self._prev_saved_count = current_count
        self._user_deleted = False

    def get_exercise_image_path(self, exercise_name):
        from kivy.app import App
        import hashlib, os

        auth_tbl.cursor.execute(
            """
            SELECT Image
            FROM user_exercises
            WHERE Name = %s
            LIMIT 1
            """,
            (exercise_name,)
        )

        row = auth_tbl.cursor.fetchone()

        # fallback
        if not row or not row["Image"]:
            return "exercisepic/default.png"

        img = row["Image"]

        if not isinstance(img, (bytes, bytearray)):
            return "exercisepic/default.png"

        # cache directory
        cache_dir = os.path.join(
            App.get_running_app().user_data_dir,
            "exercise_cache"
        )
        os.makedirs(cache_dir, exist_ok=True)

        # unique filename by image content
        filename = hashlib.md5(img).hexdigest() + ".png"
        image_path = os.path.join(cache_dir, filename)

        # write once
        if not os.path.exists(image_path):
            with open(image_path, "wb") as f:
                f.write(img)

        return image_path

    def show_admin_deleted_exercise_notice(self):
        notice = (
            "[color=#ff3333][b]An exercise was deleted[/b][/color]\n"
            "[color=#ff3333][b]by the administrator.[/b][/color]"
        )

        dialog = MDDialog(
            MDDialogHeadlineText(text="WORKOUT NOTICE"),
            MDDialogSupportingText(
                text=notice,
                markup=True,
                halign="center",
            ),
            auto_dismiss=True,
        )

        dialog.open()


    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("food_log_screen")

    def go_to_article(self):
        screen = self.manager.get_screen("article_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("article_log_screen")

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.set_user_id(self.user_id)
        self.manager.current = "calorie_counter_screen"

    def go_to_workout(self):
        screen = self.manager.get_screen("workout_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("workout_log_screen")

    def set_user_id(self, user_id):
        self.user_id = user_id

    def receive_user_id(self, user_id):
        self.user_id = user_id

        if hasattr(self, "load_user_data"):
            self.load_user_data(user_id)

    def show_snackbar(self, text, success=True):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

    def delete_exercise_confirmed(self, exercise_name):
        # 🔑 mark as user deletion
        self._user_deleted = True

        success = auth_tbl.remove_saved_exercise(self.user_id, exercise_name)

        self.dialog.dismiss()

        if success:
            self.load_saved_exercises()
            self.show_snackbar("Exercise deleted successfully!")
        else:
            self.show_snackbar("Failed to delete exercise.", success=False)

    def confirm_delete_exercise(self, exercise_name):
        self.dialog = MDDialog(
            MDDialogIcon(icon="trash-can"),
            MDDialogHeadlineText(
                text=f"Are you sure you want to delete '{exercise_name}'?"
            ),
            MDDialogSupportingText(
                text="This will be deleted from your workout log."
            ),
            MDDialogContentContainer(
                MDDivider(),
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                Widget(),  # ✅ push buttons to the right

                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: self.dialog.dismiss(),
                ),

                Widget(size_hint_x=None, width=dp(20)),  # ✅ spacing

                MDButton(
                    MDButtonText(text="Delete"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: self.delete_exercise_confirmed(
                        exercise_name
                    ),
                ),
            ),
            auto_dismiss=False,
        )

        self.dialog.open()


class SavedArticleCard(MDCard):
    article = DictProperty({})

class ArticleLogScreen(MDScreen):
    current_user_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_id = None
        self._prev_saved_count = None
        self._user_deleted = False

    def on_pre_enter(self):
        if not self.user_id:
            app = MDApp.get_running_app()
            self.user_id = app.current_user_id

        if not self.user_id:
            print("❌ No user_id set in ArticleLogScreen")
            return

        self.load_saved_articles()

    def set_user_id(self, user_id):
        self.user_id = user_id

    def load_saved_articles(self):
        app = MDApp.get_running_app()
        user_id = self.user_id

        if not user_id:
            print("No user_id set in ArticleLogScreen")
            return

        saved_list = auth_tbl.get_saved_articles(user_id)
        current_count = len(saved_list)

        # ================= ADMIN DELETE DETECTION =================
        if (
                self._prev_saved_count is not None
                and not self._user_deleted
                and current_count < self._prev_saved_count
        ):
            self.show_admin_deleted_article_notice()
        # ==========================================================

        container = self.ids.saved_articles_container
        container.clear_widgets()

        if not saved_list:
            container.add_widget(
                MDLabel(
                    text="No saved articles yet.",
                    theme_text_color="Custom",
                    text_color=(0.4, 0.4, 0.4, 1),
                    halign="center",
                    size_hint_y=None,
                    height=dp(50)
                )
            )
            return

        for article in saved_list:
            # 🔒 SANITIZE ALL FIELDS FOR UI
            safe_article = {
                "SavedId": article.get("SavedId"),
                "category": article.get("category") or "",
                "title": article.get("title") or "",
                "author": article.get("author") or "Unknown",
                "date": article.get("date") or "",
                "body": article.get("body") or "",
                "image": article.get("image") or "logo.png",
            }

            card = Factory.SavedArticleCard(
                article=safe_article,
                on_delete=lambda a=safe_article: self.confirm_delete_article(a),
                on_open=lambda a=safe_article: self.open_saved_article(a),
            )

            container.add_widget(card)
            self._prev_saved_count = current_count
            self._user_deleted = False

    def confirm_delete_article(self, article):
        self.dialog = MDDialog(
            MDDialogIcon(icon="trash-can"),
            MDDialogHeadlineText(
                text=f"Are you sure you want to remove '{article.get('title')}' ?"
            ),
            MDDialogSupportingText(
                text="This will be removed from your saved articles."
            ),
            MDDialogContentContainer(
                MDDivider(),
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                Widget(),  # push buttons to the right

                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: self.dialog.dismiss(),
                ),

                Widget(size_hint_x=None, width=dp(20)),  # space between buttons

                MDButton(
                    MDButtonText(text="Remove"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: self.delete_article_confirmed(article),
                ),
            ),
            auto_dismiss=False,
        )

        self.dialog.open()

    def delete_article_confirmed(self, article):
        # ✅ get the saved row id (based on your KV: root.article.get("SavedId"))
        saved_id = article.get("SavedId")

        if not saved_id:
            self.dialog.dismiss()
            print("ERROR: No SavedId found in article:", article)
            return

        # 🔑 MARK USER DELETE (IMPORTANT)
        self._user_deleted = True

        # ✅ correct AuthTbl method
        success = auth_tbl.delete_saved_article(saved_id)

        self.dialog.dismiss()

        if success:
            self.load_saved_articles()
            self.show_snackbar("Article removed successfully!")
        else:
            self.show_snackbar("Failed to remove article.", success=False)

    def show_admin_deleted_article_notice(self):
        notice = (
            "[color=#ff3333][b]An article was deleted[/b][/color]\n"
            "[color=#ff3333][b]by the administrator.[/b][/color]"
        )

        dialog = MDDialog(
            MDDialogHeadlineText(text="ARTICLE NOTICE"),
            MDDialogSupportingText(
                text=notice,
                markup=True,
                halign="center",
            ),
            auto_dismiss=True,  # ✅ tap anywhere to dismiss
        )

        dialog.open()

    def open_saved_article(self, article, *args):
        detail = self.manager.get_screen("article_detail_screen")
        detail.origin_screen = "article_log_screen"
        detail.set_user_id(self.user_id)

        detail.set_article(
            article.get("ArticleId"),
            article.get("category") or "",
            article.get("title") or "",
            article.get("author") or "",
            article.get("date") or "",
            article.get("body") or "",
            article.get("image") or "logo.png"
        )

        self.manager.transition.direction = "left"
        self.manager.current = "article_detail_screen"

    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("food_log_screen")

    def go_to_article(self):
        screen = self.manager.get_screen("article_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("article_log_screen")

    def go_to_workout(self):
        screen = self.manager.get_screen("workout_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("workout_log_screen")

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.set_user_id(self.user_id)
        self.manager.current = "calorie_counter_screen"

    def receive_user_id(self, user_id):
        self.user_id = user_id

        if hasattr(self, "load_user_data"):
            self.load_user_data(user_id)

    # SNACKBAR
    def show_snackbar(self, text, success=True):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.1, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()



class FeaturedCard(MDCard):
    image_source = StringProperty("")
    category = StringProperty("")
    title = StringProperty("")
    author = StringProperty("")
    date = StringProperty("")
    body_text = StringProperty("")

    def open(self):
        app = MDApp.get_running_app()
        hub = app.root.get_screen("article_hub")
        hub.open_featured_from_card(
            self.category,
            self.title,
            self.author,
            self.date,
            self.body_text,
            str(self.image_source)
        )


class ArticleHubScreen(MDScreen):
    user_id = None

    def set_user_id(self, uid):
        self.user_id = uid

    # LOAD JSON DATA ON SCREEN OPEN
    def on_enter(self, *args):
        self.populate_popular()
        self.populate_featured_carousel()

    # FEATURED CARD
    def populate_featured_carousel(self):
        from kivy.factory import Factory
        container = self.ids.featured_container
        container.clear_widgets()

        articles = [
            {
                "image": "images/img13.jpg",
                "category": "Health",
                "title": "Move More, Stress Less: Simple Exercises for a Healthier Mind and Body",
                "author": "NIDDK",
                "date": "2019",
                "body": "Healthy Eating Tips: Practical Ways to Improve Your Nutrition\n\n1. Background:\nHealthy eating is about consistent choices, not strict dieting.\n\n2. Bump Up Fiber:\n• Fruits, vegetables, whole grains, legumes\n• Snack on sliced vegetables\n• Add beans to meals\n\n3. Increase Calcium & Vitamin D:\n• Fortified dairy\n• Salmon/sardines\n• Leafy greens\n• Fortified soy products\n\n4. Add More Potassium:\n• Bananas, oranges, avocados\n• Beans & chard\n\n5. Limit Added Sugars:\n• Drink water instead of sweetened beverages\n• Read labels\n\n6. Replace Saturated Fats:\n• Use unsaturated fats (olive oil)\n• Choose lean proteins\n\n7. Reduce Sodium:\n• Use herbs & spices\n• Avoid processed foods\n\n8. Eat a Variety of Colors:\nColorful plates = diverse nutrients.\n\nReference: CDC (2024). Healthy Eating Tips.",

            },
            {
                "image": "images/img12.jpg",
                "category": "Fitness",
                "title": "Fuel Your Fitness: Eating Right to Maximize Your Workouts",
                "author": "FitnessGo",
                "date": "2024",
                "body": "Healthy Eating Tips: Practical Ways to Improve Your Nutrition\n\n1. Background:\nHealthy eating is about consistent choices, not strict dieting.\n\n2. Bump Up Fiber:\n• Fruits, vegetables, whole grains, legumes\n• Snack on sliced vegetables\n• Add beans to meals\n\n3. Increase Calcium & Vitamin D:\n• Fortified dairy\n• Salmon/sardines\n• Leafy greens\n• Fortified soy products\n\n4. Add More Potassium:\n• Bananas, oranges, avocados\n• Beans & chard\n\n5. Limit Added Sugars:\n• Drink water instead of sweetened beverages\n• Read labels\n\n6. Replace Saturated Fats:\n• Use unsaturated fats (olive oil)\n• Choose lean proteins\n\n7. Reduce Sodium:\n• Use herbs & spices\n• Avoid processed foods\n\n8. Eat a Variety of Colors:\nColorful plates = diverse nutrients.\n\nReference: CDC (2024). Healthy Eating Tips.",
            },

            {
                "image": "images/img11.jpg",
                "category": "Fitness",
                "title": "Strength and Stamina: Building Muscle Without Overdoing It",
                "author": "FitnessGo",
                "date": "2024",
                "body": "Healthy Eating Tips: Practical Ways to Improve Your Nutrition\n\n1. Background:\nHealthy eating is about consistent choices, not strict dieting.\n\n2. Bump Up Fiber:\n• Fruits, vegetables, whole grains, legumes\n• Snack on sliced vegetables\n• Add beans to meals\n\n3. Increase Calcium & Vitamin D:\n• Fortified dairy\n• Salmon/sardines\n• Leafy greens\n• Fortified soy products\n\n4. Add More Potassium:\n• Bananas, oranges, avocados\n• Beans & chard\n\n5. Limit Added Sugars:\n• Drink water instead of sweetened beverages\n• Read labels\n\n6. Replace Saturated Fats:\n• Use unsaturated fats (olive oil)\n• Choose lean proteins\n\n7. Reduce Sodium:\n• Use herbs & spices\n• Avoid processed foods\n\n8. Eat a Variety of Colors:\nColorful plates = diverse nutrients.\n\nReference: CDC (2024). Healthy Eating Tips.",
            },

            {
                "image": "images/Img14.jpg",
                "category": "Fitness",
                "title": "From Couch to 5K: Beginner’s Guide to Running Safely",
                "author": "FitnessGo",
                "date": "2024",
                "body": "Healthy Eating Tips: Practical Ways to Improve Your Nutrition\n\n1. Background:\nHealthy eating is about consistent choices, not strict dieting.\n\n2. Bump Up Fiber:\n• Fruits, vegetables, whole grains, legumes\n• Snack on sliced vegetables\n• Add beans to meals\n\n3. Increase Calcium & Vitamin D:\n• Fortified dairy\n• Salmon/sardines\n• Leafy greens\n• Fortified soy products\n\n4. Add More Potassium:\n• Bananas, oranges, avocados\n• Beans & chard\n\n5. Limit Added Sugars:\n• Drink water instead of sweetened beverages\n• Read labels\n\n6. Replace Saturated Fats:\n• Use unsaturated fats (olive oil)\n• Choose lean proteins\n\n7. Reduce Sodium:\n• Use herbs & spices\n• Avoid processed foods\n\n8. Eat a Variety of Colors:\nColorful plates = diverse nutrients.\n\nReference: CDC (2024). Healthy Eating Tips.",
            },
        ]

        for a in articles:
            card = Factory.FeaturedCard(
                image_source=a["image"],
                category=a["category"],
                title=a["title"],
                author=a["author"],
                date=a["date"],
                body_text=a.get("body", "")
            )
            container.add_widget(card)

    def open_featured_from_card(self, category, title, author, date, body, image):
        self.open_article_detail(category, title, author, date, body, image)

    def get_popular(self):
        app = MDApp.get_running_app()
        return app.articles.get("popular", [])

    def populate_popular(self):
        from kivy.metrics import dp
        from kivy.uix.image import Image
        from kivymd.uix.card import MDCard
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivymd.uix.fitimage import FitImage

        container = self.ids.popular_container
        container.clear_widgets()

        # Load from database
        articles = auth_tbl.get_all_articles()

        if not articles:
            container.add_widget(
                MDLabel(
                    text="No articles available.",
                    theme_text_color="Custom",
                    text_color=(0.4, 0.4, 0.4, 1),
                )
            )
            return

        for item in articles:
            article_id = item.get("ArticleId")  # ✅ GET ID HERE

            category = item.get("category", "") or ""
            title = item.get("title", "") or ""
            author = item.get("author", "") or ""
            date = item.get("date", "") or ""
            body = item.get("body", "") or ""
            image = str(item.get("image", "artipic_default.png") or "artipic_default.png")

            card = MDCard(
                size_hint=(1, None),
                height=dp(80),
                radius=[20, 20, 20, 20],
                elevation=0,
                md_bg_color=(0.94, 0.96, 0.92, 1),
                padding=0,
                on_release=lambda x,
                    aid=article_id,  # ✅ PASS IT
                    c=category,
                    t=title,
                    a=author,
                    d=date,
                    b=body,
                    img=image:
                self.open_article_detail(c, t, a, d, b, img, article_id=aid)

            )

            row = MDBoxLayout(
                orientation="horizontal",
                spacing=dp(8),
                padding=dp(8)
            )

            # -----------------------------
            # LEFT: IMAGE
            # -----------------------------
            thumbnail = FitImage(
                source=image,
                size_hint_x=None,
                width=dp(64),
                radius=[16, 16, 16, 16],
            )

            # -----------------------------
            # CENTER: TEXT
            # -----------------------------
            text_box = MDBoxLayout(
                orientation="vertical",
                spacing=dp(2)
            )

            category_label = MDLabel(
                text=category.upper(),
                font_size="10sp",
                bold=True,
                theme_text_color="Custom",
                text_color=(0.2, 0.45, 0.2, 1),
                shorten=True,
                max_lines=1
            )

            title_label = MDLabel(
                text=title,
                font_size="13sp",
                bold=True,
                theme_text_color="Custom",
                text_color=(0, 0, 0, 1),
                shorten=True,
                max_lines=2
            )

            date_label = MDLabel(
                text=date,
                font_size="11sp",
                theme_text_color="Custom",
                text_color=(0.45, 0.45, 0.45, 1),
                shorten=True,
                max_lines=1
            )

            text_box.add_widget(category_label)
            text_box.add_widget(title_label)
            text_box.add_widget(date_label)

            # -----------------------------
            # ASSEMBLE
            # -----------------------------
            row.add_widget(thumbnail)
            row.add_widget(text_box)
            card.add_widget(row)
            container.add_widget(card)

    # OPEN ARTICLE DETAIL SCREEN
    def open_article_detail(self, category, title, author, date_str, body_text, image, article_id=None):
        detail = self.manager.get_screen("article_detail_screen")
        detail.origin_screen = "article_hub"
        detail.set_user_id(self.user_id)

        detail.set_article(
            article_id,
            category,
            title,
            author,
            date_str,
            body_text,
            image
        )

        self.manager.transition.direction = "left"
        self.manager.current = "article_detail_screen"

    # NAVIGATION METHODS (ADD THESE IF MISSING)
    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")
        self.populate_popular()

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("food_log_screen")

    def go_to_article(self):
        screen = self.manager.get_screen("article_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("article_log_screen")

    def go_to_workout(self):
        screen = self.manager.get_screen("workout_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("workout_log_screen")

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.set_user_id(self.user_id)
        self.manager.current = "calorie_counter_screen"

    def receive_user_id(self, user_id):
        self.user_id = user_id

        if hasattr(self, "load_user_data"):
            self.load_user_data(user_id)


class ArticleDetailScreen(MDScreen):
    user_id = None
    current_article = {}
    origin_screen = StringProperty("article_hub")

    def set_user_id(self, user_id):  # ✅ NEW: Method to set user_id explicitly
        self.user_id = user_id

    def save_article_from_detail(self):
        user_id = self.user_id
        if not user_id:
            return

        article = self.current_article
        if not article:
            return

        btn = self.ids.save_btn

        # 🔁 TOGGLE (same logic as workout heart)
        if btn.icon == "bookmark-outline":
            # ✅ SAVE
            success = auth_tbl.save_article(user_id, article)
            if success:
                btn.icon = "bookmark"
        else:
            # ❌ UNSAVE
            title = article.get("title")
            saved_id = auth_tbl.get_saved_article_id(user_id, title)

            if saved_id:
                auth_tbl.delete_saved_article(saved_id)
                btn.icon = "bookmark-outline"

                # ✅ IMPORTANT: tell ArticleLogScreen this was USER action
                try:
                    log = self.manager.get_screen("article_log_screen")
                    log._user_deleted = True
                except Exception:
                    pass

    def set_article(
            self,
            article_id=None,
            category="",
            title="",
            author="",
            date_str="",
            body_text="",
            image_source="logo.png"
    ):
        # ✅ STORE ARTICLE (SAFE)
        self.current_article = {
            "ArticleId": article_id,
            "category": category or "",
            "title": title or "",
            "author": author or "Unknown",
            "date": date_str or "",
            "body": body_text or "",
            "image": image_source or "logo.png",
        }

        # ✅ UPDATE UI (NO NONE VALUES)
        self.ids.ad_category.text = category or ""
        self.ids.ad_title.text = title or ""
        self.ids.ad_author.text = author or "Unknown"
        self.ids.ad_date.text = date_str or ""
        self.ids.ad_body.text = body_text or ""
        self.ids.ad_image.source = image_source or "logo.png"

        # Resize body safely
        self.ids.ad_body.texture_update()
        self.ids.ad_body.height = self.ids.ad_body.texture_size[1]

        self.check_if_saved()

    def check_if_saved(self):
        user_id = self.user_id

        if not user_id or not self.current_article:
            return

        saved_articles = auth_tbl.get_saved_articles(user_id)

        if any(a["title"] == self.current_article["title"] for a in saved_articles):
            self.ids.save_btn.icon = "bookmark"
        else:
            self.ids.save_btn.icon = "bookmark-outline"

    def on_pre_enter(self, *args):
        if not self.user_id:
            app = MDApp.get_running_app()
            self.user_id = getattr(app, "current_user_id", None)

        body = self.ids.ad_body
        body.texture_update()
        body.height = body.texture_size[1]

        self.check_if_saved()

#changemoto
    def go_back(self):
        self.manager.transition.direction = "right"

        if self.origin_screen == "article_log_screen":
            self.manager.current = "article_log_screen"
        else:
            # default fallback
            self.manager.current = "article_hub"

class WorkoutProgramScreen(MDScreen):
    user_id = None
    selected_program = None  # ← store selected program

    def on_pre_enter(self, *args):
        if self.user_id and self.selected_program:
            self.load_program(self.user_id, self.selected_program)

    @staticmethod
    def format_exercise_name(name):
        name = name.strip(" -")
        return " ".join(word.capitalize() for word in name.split())

    def load_program(self, user_id, program_name):
        # ----------------------------
        # PARSE PROGRAM NAME
        # ----------------------------
        parts = program_name.split()
        level = parts[-1].lower()
        goal = "_".join(parts[:-1]).lower()

        # ----------------------------
        # USER CONDITION
        # ----------------------------
        user_data = auth_tbl.get_user_goal(user_id)
        has_condition = user_data["condition"] if user_data else False

        # ----------------------------
        # LOAD EXERCISES (NO MODE FILTER)
        # ----------------------------
        auth_tbl.cursor.execute(
            """
            SELECT Name, Sets, Reps, RestSeconds, ProgramName
            FROM user_exercises
            WHERE UserId = 0
              AND Goal = %s
              AND Difficulty = %s
            ORDER BY Created_at ASC
            """,
            (goal, level)
        )

        db_rows = auth_tbl.cursor.fetchall()

        # ----------------------------
        # SPLIT EXERCISES BY MODE
        # ----------------------------
        program = {"normal": [], "condition": []}

        for r in db_rows:
            bucket = normalize_program_name(r["ProgramName"])

            program[bucket].append({
                "name": r["Name"],
                "sets": r["Sets"],
                "reps": r["Reps"],
                "rest": r["RestSeconds"],
            })

        # ----------------------------
        # CHOOSE EXERCISES FOR USER
        # ----------------------------
        exercises = program["condition"] if has_condition else program["normal"]

        # ----------------------------
        # SET PROGRAM HEADER
        # ----------------------------
        banner_map = {
            "beginner": "beginner.jpg",
            "intermediate": "intermediate.jpg",
            "advanced": "advanced.jpg"
        }

        self.ids.program_image.source = banner_map.get(level, "program_banner.png")
        self.ids.program_details.text = f"{level.title()} | {len(exercises)} Workouts"

        # ----------------------------
        # LOAD EXERCISES UI
        # ----------------------------
        container = self.ids.fl_container
        container.clear_widgets()

        if not exercises:
            container.add_widget(MDBoxLayout(size_hint_y=None, height="120dp"))
            container.add_widget(
                MDLabel(
                    text="No exercises available",
                    halign="center",
                    theme_text_color="Hint",
                )
            )
            return

        # ----------------------------
        # FAVORITES
        # ----------------------------
        saved_exercises = auth_tbl.get_saved_exercises(user_id)
        saved_names = {row["name"] for row in saved_exercises}

        # ----------------------------
        # RENDER EXERCISES
        # ----------------------------
        for ex in exercises:
            heart_icon = "heart" if ex["name"] in saved_names else "heart-outline"

            heart_btn = MDIconButton(
                icon=heart_icon,
                on_release=lambda btn, e=ex: self.toggle_favorite(btn, e, None)
            )

            img_path = self.get_exercise_image_path(ex["name"])

            # 🔹 IMAGE (LEFT)
            thumb = FitImage(
                source=img_path,
                size_hint=(None, None),
                size=(dp(48), dp(48)),
                radius=[12, 12, 12, 12],
            )

            # 🔹 TEXT
            title = MDLabel(
                text=ex["name"],
                bold=True,
                halign="left",
            )

            subtitle = MDLabel(
                text=f"{ex['reps']} Reps × {ex['sets']} Sets   Rest: {ex['rest']}s",
                theme_text_color="Secondary",
                font_size="12sp",
                halign="left",
            )

            text_box = MDBoxLayout(
                orientation="vertical",
                spacing=dp(2),
                size_hint_x=1,
            )
            text_box.add_widget(title)
            text_box.add_widget(subtitle)

            # 🔹 ROW
            row = MDBoxLayout(
                orientation="horizontal",
                spacing=dp(12),
                padding=(dp(12), dp(10), dp(12), dp(10)),
            )

            row.add_widget(thumb)
            row.add_widget(text_box)
            row.add_widget(heart_btn)

            # 🔹 CARD
            card = MDCard(
                row,
                size_hint_y=None,
                height=dp(78),
                radius=[18, 18, 18, 18],
                md_bg_color=(0.95, 0.96, 0.92, 1),
                ripple_behavior=True,
                on_release=lambda x, e=ex: self.open_exercise_detail(e),
            )

            container.add_widget(card)

    def get_exercise_image_path(self, exercise_name):
        from kivy.app import App
        import hashlib, os

        auth_tbl.cursor.execute(
            """
            SELECT Image
            FROM user_exercises
            WHERE Name = %s
            LIMIT 1
            """,
            (exercise_name,)
        )

        row = auth_tbl.cursor.fetchone()

        if not row or not row["Image"]:
            return "exercisepic/default.png"

        img = row["Image"]

        if not isinstance(img, (bytes, bytearray)):
            return "exercisepic/default.png"

        cache_dir = os.path.join(
            App.get_running_app().user_data_dir,
            "exercise_cache"
        )
        os.makedirs(cache_dir, exist_ok=True)

        filename = hashlib.md5(img).hexdigest() + ".png"
        image_path = os.path.join(cache_dir, filename)

        if not os.path.exists(image_path):
            with open(image_path, "wb") as f:
                f.write(img)

        return image_path

    def open_exercise_detail(self, exercise):
        screen = self.manager.get_screen("exercise_detail_screen")
        screen.user_id = self.user_id
        screen.program_name = self.selected_program
        screen.source_screen = "workout_program_screen"  # ✅ ADD
        screen.set_exercise(exercise)

        self.manager.instant_switch("exercise_detail_screen")

    def toggle_favorite(self, btn, exercise, user_exercise_id):
        if not self.user_id:
            return

        if btn.icon == "heart-outline":
            btn.icon = "heart"
            auth_tbl.add_saved_exercise(self.user_id, exercise, self.selected_program, None)
        else:
            btn.icon = "heart-outline"

            auth_tbl.remove_saved_exercise(self.user_id, exercise["name"])

            # ✅ IMPORTANT LINE (THIS IS THE FIX)
            log_screen = self.manager.get_screen("workout_log_screen")
            log_screen._user_deleted = True

    def set_user_id(self, user_id):
        self.user_id = user_id

    def load_user_exercises(self, user_id, goal, level, mode):
        auth_tbl.cursor.execute(
            """
            SELECT Name, Sets, Reps, RestSeconds
            FROM user_exercises
            WHERE (UserId IS NULL OR UserId=%s)
              AND Goal=%s
              AND Difficulty=%s
            ORDER BY Created_at ASC
            """,
            (user_id, goal, level)
        )

        rows = auth_tbl.cursor.fetchall()

        exercises = []
        for r in rows:
            exercises.append({
                "name": r["Name"],
                "sets": r["Sets"],
                "reps": r["Reps"],
                "rest": r["RestSeconds"],
            })

        # 👇 This already exists in your user screen
        self.load_exercises(exercises)

    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_stories_hub(self):
        screen = self.manager.get_screen("stories_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("stories_hub")

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("food_log_screen")

    def go_to_article(self):
        screen = self.manager.get_screen("article_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("article_log_screen")

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("calorie_counter_screen")

    def go_to_workout(self):
        screen = self.manager.get_screen("workout_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("workout_log_screen")

    def receive_user_id(self, user_id):
        self.user_id = user_id

        if hasattr(self, "load_user_data"):
            self.load_user_data(user_id)


class ExercisesHubScreen(MDScreen):
    user_id = None

    # ---------- NAV BUTTONS ----------
    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_stories_hub(self):
        screen = self.manager.get_screen("stories_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("stories_hub")

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("food_log_screen")

    def go_to_article(self):
        screen = self.manager.get_screen("article_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_log_screen")

    def go_to_calorie_counter(self):
        screen = self.manager.get_screen("calorie_counter_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("calorie_counter_screen")

    def go_to_workout(self):
        screen = self.manager.get_screen("workout_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("workout_log_screen")

    def set_user_id(self, user_id):
        self.user_id = user_id

    def receive_user_id(self, user_id):
        self.set_user_id(user_id)

    def open_program_details(self, program_name):
        screen = self.manager.get_screen("workout_program_screen")
        screen.set_user_id(self.user_id)
        screen.selected_program = program_name
        self.manager.instant_switch("workout_program_screen")

    def on_pre_enter(self, *args):
        if not self.user_id:
            return

        # ----------------------------
        # GET USER GOAL & CONDITION
        # ----------------------------
        user_data = auth_tbl.get_user_goal(self.user_id)
        if not user_data:
            return

        goal = user_data["goal"]  # e.g. "lose_weight"
        has_condition = user_data["condition"]  # True / False

        # 🔥 MAP MODE → ACTUAL DB VALUE
        program_name_filter = (
            "health condition" if has_condition else "normal"
        )

        # ----------------------------
        # CLEAR UI
        # ----------------------------
        container = self.ids.fl_container
        container.clear_widgets()

        # ----------------------------
        # DIFFICULTY LEVELS
        # ----------------------------
        levels = ["beginner", "intermediate", "advanced"]

        for level_name in levels:
            auth_tbl.cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM user_exercises
                WHERE UserId = 0
                  AND Goal = %s
                  AND Difficulty = %s
                  AND LOWER(TRIM(ProgramName)) = %s
                """,
                (
                    goal,
                    level_name,
                    program_name_filter  # ✅ CORRECT VALUE
                )
            )

            row = auth_tbl.cursor.fetchone()
            total_workouts = row["total"] if row else 0

            program_name = f"{goal.replace('_', ' ').title()} {level_name.title()}"

            self.add_program_card(
                program_name=program_name,
                difficulty=level_name,
                total_workouts=total_workouts
            )

    def add_program_card(self, program_name, difficulty, total_workouts):

        # Choose the banner image based on difficulty
        banner_map = {
            "beginner": "beginner.jpg",
            "intermediate": "intermediate.jpg",
            "advanced": "advanced.jpg"
        }

        # Default fallback if something is missing
        banner_image = banner_map.get(difficulty.lower(), "program_banner.png")

        quote_map = {
            "beginner": "Consistency beats perfection every time.",
            "intermediate": "Train with purpose!. Grow with discipline!.",
            "advanced": "Your mindset is your strongest muscle!."
        }

        quote = quote_map.get(difficulty.lower(), "")

        card = MDCard(
            size_hint_y=None,
            height="200dp",
            radius=[20, 20, 20, 20],
            padding=10,
            elevation=3,
            on_release=lambda x: self.open_program_details(program_name)
        )

        layout = MDBoxLayout(orientation="vertical", spacing=5)

        image_card = MDCard(
            size_hint_y=None,
            height="140dp",
            radius=[20, 20, 20, 20],  # Rounded corners for the image
            padding=0,
            elevation=0,
            on_release=lambda x: self.open_program_details(program_name)
        )

        image_card.add_widget(FitImage(
            source=banner_image,
            keep_ratio=False,
            allow_stretch=True
        ))

        layout.add_widget(image_card)

        layout.add_widget(MDLabel(
            text=f"[b]{quote}[/b]",
            markup=True,
            font_size="12sp",
            theme_text_color="Secondary",
            halign="left"
        ))

        layout.add_widget(MDLabel(
            text=f"{difficulty.title()} | {total_workouts} Workouts",
            font_size="12sp",
            halign="left"
        ))

        card.add_widget(layout)
        self.ids.fl_container.add_widget(card)


class ExerciseDetailScreen(MDScreen):
    user_id = None
    current_exercise = None
    program_name = None
    source_screen = None

    def open_exercise_detail(self, exercise_name):
        screen = self.manager.get_screen("exercise_detail_screen")
        screen.user_id = self.user_id
        screen.load_exercise(exercise_name)

        self.manager.transition.direction = "left"
        self.manager.current = "exercise_detail_screen"

    def set_exercise(self, exercise):
        self.current_exercise = exercise
        name = exercise.get("name", "")

        if not name:
            print("❌ Exercise name missing")
            return

        # ----------------------------
        # FETCH DETAILS FROM DATABASE
        # ----------------------------
        auth_tbl.cursor.execute(
            """
            SELECT Meaning, Steps, Benefits, Image
            FROM user_exercises
            WHERE Name = %s
            ORDER BY UserId IS NOT NULL
            LIMIT 1
            """,
            (name,)
        )

        row = auth_tbl.cursor.fetchone()

        if not row:
            print(f"❌ No details found in DB for exercise: {name}")
            return

        # ----------------------------
        # SET TEXT CONTENT
        # ----------------------------
        self.ids.exercise_title.text = name
        self.ids.exercise_meaning.text = row["Meaning"] or ""

        self.ids.exercise_steps.text = "\n".join(
            f"{i + 1}. {step}"
            for i, step in enumerate((row["Steps"] or "").splitlines())
        )

        self.ids.exercise_benefits.text = "\n".join(
            f"• {benefit}"
            for benefit in (row["Benefits"] or "").splitlines()
        )

        # ----------------------------
        # IMAGE (BLOB bytes → file → show)
        # ----------------------------
        from kivy.app import App
        import hashlib

        image_widget = self.ids.exercise_image

        img = row["Image"]

        # default fallback
        image_path = os.path.join("exercisepic", "default.png")

        if img:
            try:
                # If it's bytes/blob (most likely in your case)
                if isinstance(img, (bytes, bytearray)):
                    # detect extension by signature
                    if img.startswith(b"\xff\xd8\xff"):
                        ext = ".jpg"
                    elif img.startswith(b"\x89PNG"):
                        ext = ".png"
                    else:
                        ext = ".img"

                    # save into app writable folder
                    cache_dir = os.path.join(App.get_running_app().user_data_dir, "exercise_cache")
                    os.makedirs(cache_dir, exist_ok=True)

                    # unique filename based on content
                    fname = hashlib.md5(img).hexdigest() + ext
                    image_path = os.path.join(cache_dir, fname)

                    # write only if not exists
                    if not os.path.exists(image_path):
                        with open(image_path, "wb") as f:
                            f.write(img)

                else:
                    # If DB stored a filename/path (string)
                    image_file = str(img).strip()
                    image_path = os.path.join("exercisepic", image_file)

            except Exception as e:
                print("❌ Image load error:", e)
                image_path = os.path.join("exercisepic", "default.png")

        image_widget.source = image_path
        image_widget.reload()

        # ----------------------------
        # FAVORITE STATUS
        # ----------------------------
        self.check_if_saved()

    def check_if_saved(self):
        if not self.user_id or not self.current_exercise:
            return

        saved = auth_tbl.get_saved_exercises(self.user_id)
        saved_names = {ex["name"] for ex in saved}

        self.ids.exercise_heart_btn.icon = (
            "heart" if self.current_exercise["name"] in saved_names
            else "heart-outline"
        )

    def go_back(self):
        self.manager.transition.direction = "right"

        if self.source_screen == "workout_log_screen":
            self.manager.current = "workout_log_screen"
        else:
            # default → program screen
            self.manager.current = "workout_program_screen"

    def toggle_exercise_favorite(self):
        btn = self.ids.exercise_heart_btn

        if not self.user_id or not self.current_exercise:
            return

        if btn.icon == "heart-outline":
            btn.icon = "heart"
            auth_tbl.add_saved_exercise(
                self.user_id,
                self.current_exercise,  # ✅ full dict
                self.program_name,  # ✅ program name
                None
            )
        else:
            btn.icon = "heart-outline"
            auth_tbl.remove_saved_exercise(
                self.user_id,
                self.current_exercise["name"]
            )

class ProfileScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # OTP tracking
        self.generated_otp = ""
        self.otp_created_at = None
        self.OTP_VALIDITY_SECONDS = 300
        self.timer_event = None
        self.otp_fields = []

    user_id = None
    selected_image_path = StringProperty(None)
    photo_bytes = None

    def force_exercise_refresh(self):
        app = MDApp.get_running_app()
        sm = app.root

        # Refresh Exercise Hub (program list)
        exercise_hub = sm.get_screen("exercise_hub")
        exercise_hub.on_pre_enter()

        # Clear Workout Log
        workout_log = sm.get_screen("workout_log_screen")
        workout_log.load_saved_exercises()

        # Reset program screen
        program_screen = sm.get_screen("workout_program_screen")
        program_screen.selected_program = None

    def set_user_id(self, user_id):
        self.user_id = user_id

    def on_pre_enter(self):
        self.load_profile_data()

    # LOAD USER PROFILE INFORMATION
    def load_profile_data(self):
        if not self.user_id:
            print("No user_id passed to ProfileScreen")
            return

        # LOAD PHOTO
        try:
            photo_bytes = auth_tbl.get_user_photo(self.user_id)

            if photo_bytes:
                buffer = io.BytesIO(photo_bytes)
                texture = CoreImage(buffer, ext="png").texture
                self.ids.user_profile_picture.source = ""
                self.ids.user_profile_picture.texture = texture

            else:
                # If no photo exists, load a default image
                print("User has no profile image, using default.")
                self.ids.user_profile_picture.source = "profile_default.png"

        except Exception as e:
            print("Error loading profile photo:", e)
            self.ids.user_profile_picture.source = "profile_default.png"

        # LOAD NAME
        try:
            fullname = auth_tbl.get_user_fullname(self.user_id)
            if fullname:
                self.ids.user_name_profile.text = fullname
        except Exception as e:
            print("Error loading user name:", e)

        # LOAD GOAL DATA
        try:
            query = """
                SELECT Goal, DailyNetGoal, DesiredWeight, BMI
                FROM data_db
                WHERE UserId = %s
            """
            auth_tbl.cursor.execute(query, (self.user_id,))
            result = auth_tbl.cursor.fetchone()

            if result:
                fitness_goal = result["Goal"] or "N/A"
                daily_calorie = result["DailyNetGoal"] or 0
                goal_weight = result["DesiredWeight"] or 0
                bmi = result["BMI"] or 0

                self.ids.fitness_goal_label.text = fitness_goal
                self.ids.daily_calorie_label.text = f"{daily_calorie:,.0f} cal"
                self.ids.desired_weight_label.text = f"{int(goal_weight)} kg"
                self.ids.bmi_label.text = f"BMI: {bmi:.2f}"  # Adding BMI label, non-editable

        except Exception:
            pass

    # PHOTO CROP
    def make_image_circle(self, path):
        img = PILImage.open(path).convert("RGBA")
        size = min(img.size)
        img = ImageOps.fit(img, (size, size))

        mask = PILImage.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    # OPEN FILECHOOSER
    def open_file_chooser(self):
        filechooser.open_file(on_selection=self.on_image_selected)

    # HANDLE IMAGE
    def on_image_selected(self, selection):
        if not selection:
            return

        path = selection[0]
        ext = os.path.splitext(path)[1].lower()

        # ❌ BLOCK VIDEOS
        if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"):
            self.show_snackbar(
                "Videos are not allowed. Please select an image.",
                success=False
            )
            return

        # ❌ BLOCK NON-IMAGE FILES
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            self.show_snackbar(
                "Invalid file type. Please select an image.",
                success=False
            )
            return

        # ✅ IMAGE IS VALID
        try:
            buffer = self.make_image_circle(path)

            self.ids.user_profile_picture.texture = CoreImage(
                buffer, ext="png"
            ).texture

            self.photo_bytes = buffer.getvalue()

            # SAVE TO DATABASE
            result = auth_tbl.update_photo(self.user_id, self.photo_bytes)

            if result:
                self.show_snackbar("Profile photo updated successfully!", success=True)
            else:
                self.show_snackbar("Failed to update profile photo.", success=False)

        except Exception as e:
            print("Image processing error:", e)
            self.show_snackbar("Failed to load image.", success=False)

    # DROPDOWN → OPEN EDIT GOALS DIALOG
    def show_edit_goals_dropdown(self, *args):
        caller = self.ids.dots_icon

        items = [
            {"text": "Edit Goals", "on_release": lambda x="Edit Goals": self._on_edit_goals_selected()}
        ]

        self._edit_goals_menu = MDDropdownMenu(
            caller=caller,
            items=items,
            width_mult=3
        )
        self._edit_goals_menu.open()

    def _on_edit_goals_selected(self):
        try:
            self._edit_goals_menu.dismiss()
        except:
            pass
        self.open_edit_goals_dialog()

    # EDIT GOALS DIALOG (AUTO-CALCULATING)
    def open_edit_goals_dialog(self):
        user_info = auth_tbl.get_user_goal_info(self.user_id)
        if not user_info:
            print("Failed to fetch goal info")
            return

        current_goal = user_info["Goal"]
        current_desired = str(user_info["DesiredWeight"])
        current_daily = str(user_info["DailyNetGoal"])

        if float(current_desired).is_integer():
            current_desired = str(int(float(current_desired)))

        # Create fields
        self.goal_field = MDTextField(
            text=current_goal,
            hint_text="Goal",
            readonly=True
        )

        self.weight_field = MDTextField(
            text=current_desired,
            hint_text="Desired Weight (kg)",
            input_filter="float"
        )

        self.daily_field = MDTextField(
            text=current_daily,
            hint_text="Daily Calorie Goal",
            readonly=True,
            disabled=True
        )

        # LIVE RECALCULATION TRIGGERS
        self.weight_field.bind(text=self.recalculate_live)

        # dropdown for goal
        self.goal_field.bind(on_touch_down=self.open_goal_dropdown)

        # --------------------------------------------------
        # ✅ AUTO-SET & LOCK WEIGHT FOR KEEP FIT (ADD THIS)
        # --------------------------------------------------
        if normalize_goal(current_goal) == "keep_fit":
            info = auth_tbl.get_user_complete_info(self.user_id)
            if info:
                self.weight_field.text = str(int(info["Weight"]))
                self.weight_field.disabled = True
        else:
            self.weight_field.disabled = False
        # --------------------------------------------------

        # dialog UI
        self.goals_dialog = MDDialog(
            MDDialogIcon(icon="pencil"),
            MDDialogHeadlineText(text="Edit Fitness Goals"),

            MDDialogContentContainer(
                MDLabel(text="Goal", bold=True),
                self.goal_field,

                MDLabel(text="Desired Weight", bold=True),
                self.weight_field,

                MDLabel(text="Daily Calorie Goal", bold=True),
                self.daily_field,

                orientation="vertical",
                spacing="15dp",
                padding="14dp",
            ),

            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.goals_dialog.dismiss()
                ),
                MDButton(
                    MDButtonText(text="Update"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.update_user_goals()
                ),
                spacing="10"
            ),
            auto_dismiss=False
        )

        self.goals_dialog.open()

        # 🔁 Initial live calculation (KEEP THIS)
        self.recalculate_live()

    # GOAL DROPDOWN
    def open_goal_dropdown(self, instance, touch):
        if instance.collide_point(*touch.pos):
            items = ["Lose Weight", "Keep Fit",
                     "Gain Weight", "Gain Muscles"]

            menu_items = [
                {"text": goal, "on_release": lambda x=goal: self.select_goal(x)}
                for goal in items
            ]

            self.goal_menu = MDDropdownMenu(
                caller=self.goal_field,
                items=menu_items,
                width_mult=4
            )
            self.goal_menu.open()

    def select_goal(self, goal):
        self.goal_field.text = goal
        self.goal_menu.dismiss()

        info = auth_tbl.get_user_complete_info(self.user_id)
        if not info:
            return

        current_weight = float(info["Weight"])

        # ✅ AUTO-SET desired weight for Keep Fit
        if normalize_goal(goal) == "keep_fit":
            self.weight_field.text = str(int(current_weight))
            self.weight_field.disabled = True
        else:
            self.weight_field.disabled = False

        # 🔁 RECALCULATE calories immediately
        self.recalculate_live()

    # LIVE CALCULATOR
    def recalculate_live(self, *args):
        try:
            # Fetch the user's info
            info = auth_tbl.get_user_complete_info(self.user_id)
            if not info:
                return

            weight = info["Weight"]
            height = info["Height"]
            age = info["Age"]
            gender = info["Gender"]
            activity = info["ActivityLevel"]

            # Normalize selected goal
            goal = normalize_goal(self.goal_field.text)

            # ✅ KEEP FIT: force desired weight = current weight
            if goal == "keep_fit":
                desired_weight_value = float(weight)
                self.weight_field.text = str(int(weight))
                self.weight_field.disabled = True
            else:
                self.weight_field.disabled = False

                # 🔒 KEEP YOUR VALIDATION
                desired_weight = self.weight_field.text.strip()
                try:
                    desired_weight_value = float(desired_weight)
                except ValueError:
                    self.show_snackbar("Desired weight must be a valid number.")
                    return

            # 🔁 Recalculate calories
            new_calories = auth_tbl.recalculate_daily_goal(
                weight,
                height,
                age,
                gender,
                activity,
                goal,
                desired_weight_value
            )

            # ✅ Display updated daily calorie
            self.daily_field.text = str(round(new_calories))

        except Exception as e:
            print("Error recalculating live goal:", e)
            self.daily_field.text = ""

    def update_user_goals(self):
        # ✅ normalize once, use consistently
        goal = normalize_goal(self.goal_field.text)
        desired_w = self.weight_field.text.strip()

        # Required
        if not goal:
            self.show_snackbar("Please select your goal.")
            return

        if not desired_w:
            self.show_snackbar("Desired weight is required.")
            return

        # Number validation
        try:
            desired_weight_value = float(desired_w)
            if desired_weight_value <= 0:
                self.show_snackbar("Please enter a valid desired weight.")
                return
        except ValueError:
            self.show_snackbar("Desired weight must be a number.")
            return

        # Get current weight
        info = auth_tbl.get_user_complete_info(self.user_id)
        if not info:
            self.show_snackbar("Error fetching current weight.")
            return

        current_weight = float(info["Weight"])

        # ---------- SMART GOAL VALIDATION ----------
        if goal == "lose_weight":
            if desired_weight_value >= current_weight:
                self.show_snackbar(
                    f"Must be less than your current weight ({current_weight} kg)."
                )
                return

        elif goal in ["gain_weight", "gain_muscle"]:
            if desired_weight_value <= current_weight:
                self.show_snackbar(
                    f"Must be greater than your current weight ({current_weight} kg)."
                )
                return

        elif goal == "keep_fit":
            if desired_weight_value != current_weight:
                self.show_snackbar(
                    f"Must be the same as your current weight ({current_weight} kg)."
                )
                return

        # -----------------------------------------

        # --- CONFIRMATION ---
        def confirm_update(instance):
            self.goals_dialog.dismiss()
            self._save_user_goals(goal, desired_weight_value)
            self.confirm_dialog.dismiss()

        self.confirm_dialog = MDDialog(
            MDDialogHeadlineText(text="Are you sure?"),
            MDDialogSupportingText(
                text=(
                    "This will recalculate your daily calorie net goals "
                    "and overwrite any custom settings. Would you like to continue?"
                )
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="No"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.confirm_dialog.dismiss()
                ),
                MDButton(
                    MDButtonText(text="Yes"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=confirm_update
                ),
                spacing="10dp"
            ),
            auto_dismiss=False
        )

        self.confirm_dialog.open()

    def _save_user_goals(self, goal, desired_weight_value):
        info = auth_tbl.get_user_complete_info(self.user_id)

        new_daily_goal = auth_tbl.recalculate_daily_goal(
            info["Weight"],
            info["Height"],
            info["Age"],
            info["Gender"],
            info["ActivityLevel"],
            goal,
            desired_weight_value
        )

        result = auth_tbl.update_user_goals(
            self.user_id, goal, desired_weight_value, new_daily_goal
        )

        if result:
            # 🔑 MARK AS USER-INITIATED CHANGE (PREVENT ADMIN NOTICE)
            try:
                app = MDApp.get_running_app()
                log = app.root.get_screen("workout_log_screen")
                log._user_deleted = True
            except Exception:
                pass

            # 🔥 CLEAR EXERCISE LOG
            auth_tbl.clear_user_saved_exercises(self.user_id)

            # 🔁 REFRESH UI
            self.force_exercise_refresh()

            self.load_profile_data()
            self.show_snackbar("Goals updated successfully!")
    # SNACKBAR
    def show_snackbar(self, text, success=True):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),  # ← pure white
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="40dp",
            pos_hint={"center_x": 0.5, "y": 0.05},
            md_bg_color=(0.1, 0.1, 0.1, 1),  # Dark background looks cleaner
            radius=[20, 20, 20, 20],
        )
        snack.open()

    # --- EDIT PROFILE DIALOG ---
    def open_edit_profile_dialog(self):
        query = """
            SELECT Username, Fullname, Email, Age, Gender, Height, Weight,
                   ActivityLevel, HasHealthConditions, WhatHealthConditions,
                   BMI, BMIStatus
            FROM data_db
            WHERE UserId = %s
        """
        auth_tbl.cursor.execute(query, (self.user_id,))
        user = auth_tbl.cursor.fetchone()

        if not user:
            return

        self.username_field = MDTextField(text=user["Username"], hint_text="Username")
        self.fullname_field = MDTextField(text=user["Fullname"], hint_text="Fullname")
        self.age_field = MDTextField(text=str(user["Age"]), hint_text="Age", input_filter="int")

        self.height_field = MDTextField(
            text=str(int(user["Height"])),
            hint_text="Height (cm)",
            input_filter="int"
        )
        self.weight_field = MDTextField(
            text=str(int(user["Weight"])),
            hint_text="Weight (kg)",
            input_filter="int"
        )

        self.gender_field = MDTextField(text=user["Gender"], hint_text="Gender", readonly=True)
        self.email_field = MDTextField(text=user["Email"], hint_text="Email", readonly=True)


        # ✅ DROPDOWNS (FIXED)
        self.activity_field = MDTextField(text=user["ActivityLevel"], hint_text="Activity Level")
        self.health_field = MDTextField(text=user["HasHealthConditions"], hint_text="Has Health Condition?")
        self.condition_field = MDTextField(
            text=user["WhatHealthConditions"] or "",
            hint_text="Specific Condition"
        )

        self.condition_field.disabled = (user["HasHealthConditions"] == "No")

        # ✅ BIND DROPDOWNS
        self.activity_field.bind(on_touch_down=self.open_activity_dropdown)
        self.health_field.bind(on_touch_down=self.open_health_dropdown)

        self.bmi_label = MDLabel(
            text=f"{user['BMI']} | {user['BMIStatus']}",
            halign="center",
            size_hint_y=None,
            height="40dp"
        )

        layout = BoxLayout(
            orientation="vertical",
            spacing=dp(14),
            padding=dp(14),
            size_hint_y=None
        )
        layout.bind(minimum_height=layout.setter("height"))

        fields = [
            ("Username", self.username_field),
            ("Fullname", self.fullname_field),
            ("Email", self.email_field),
            ("Age", self.age_field),
            ("Gender", self.gender_field),
            ("Height (cm)", self.height_field),
            ("Weight (kg)", self.weight_field),
            ("Activity Level", self.activity_field),
            ("Has Health Condition?", self.health_field),
            ("Specific Condition", self.condition_field),
            ("BMI", self.bmi_label),
        ]

        for label, field in fields:
            layout.add_widget(MDLabel(text=label, bold=True))
            layout.add_widget(field)

        scroll = MDScrollView(size_hint_y=None, height=dp(350))
        scroll.add_widget(layout)

        self.profile_dialog = MDDialog(
            MDDialogIcon(icon="account-edit"),
            MDDialogHeadlineText(text="Edit Profile"),
            MDDialogContentContainer(scroll),
            MDDialogButtonContainer(
                Widget(),
                MDButton(MDButtonText(text="Cancel"), style="filled", theme_bg_color="Custom", md_bg_color=(0.6, 0.8, 0.6, 1), on_release=lambda x: self.profile_dialog.dismiss()),
                MDButton(MDButtonText(text="Update"), style="filled", theme_bg_color="Custom",  md_bg_color=(0.1, 0.7, 0.1, 1), on_release=lambda x: self.update_user_profile()),
                spacing="10dp"
            ),
            auto_dismiss=False
        )
        self.profile_dialog.open()

    def open_gender_dropdown(self, instance, touch):
        if instance.collide_point(*touch.pos):
            items = ["Male", "Female"]
            menu_items = [{"text": g, "on_release": lambda x=g: self.set_gender(x)} for g in items]

            self.gender_menu = MDDropdownMenu(caller=self.gender_field, items=menu_items, width_mult=3)
            self.gender_menu.open()

    def set_gender(self, value):
        self.gender_field.text = value
        self.gender_menu.dismiss()

    def open_activity_dropdown(self, instance, touch):
        if instance.collide_point(*touch.pos):
            items = ["Active", "Not Very Active", "Lightly Active", "Very Active"]
            menu_items = [{"text": a, "on_release": lambda x=a: self.set_activity(x)} for a in items]

            self.activity_menu = MDDropdownMenu(caller=self.activity_field, items=menu_items, width_mult=4)
            self.activity_menu.open()

    def set_activity(self, value):
        self.activity_field.text = value
        self.activity_menu.dismiss()

    def open_health_dropdown(self, instance, touch):
        if instance.collide_point(*touch.pos):
            items = ["Yes", "No"]
            self.health_menu = MDDropdownMenu(
                caller=self.health_field,
                items=[{"text": i, "on_release": lambda x=i: self.set_health(x)} for i in items],
                width_mult=3
            )
            self.health_menu.open()

    def set_health(self, value):
        self.health_field.text = value
        self.condition_field.disabled = (value == "No")
        if value == "No":
            self.condition_field.text = ""
        self.health_menu.dismiss()

    def update_user_profile(self):
        username = self.username_field.text.strip()
        fullname = self.fullname_field.text.strip()
        age = self.age_field.text.strip()
        gender = self.gender_field.text.strip()
        height = self.height_field.text.strip()
        weight = self.weight_field.text.strip()
        activity = self.activity_field.text.strip()
        has_condition = self.health_field.text.strip()
        condition = self.condition_field.text.strip() if has_condition == "Yes" else None

        # 🔹 GET OLD CONDITION BEFORE UPDATE
        auth_tbl.cursor.execute(
            """
            SELECT HasHealthConditions, WhatHealthConditions
            FROM data_db
            WHERE UserId = %s
            """,
            (self.user_id,)
        )
        old_data = auth_tbl.cursor.fetchone()

        old_has_condition = old_data["HasHealthConditions"] if old_data else None
        old_condition = old_data["WhatHealthConditions"] if old_data else None

        # 🔒 VALIDATE HEALTH CONDITION AGAINST SUPPORTED LIST
        if has_condition == "Yes":
            if not condition:
                self.show_snackbar("Please specify your health condition.")
                return

            # Normalize input (spaces → underscores, lowercase)
            normalized_condition = condition.strip().lower().replace(" ", "_")

            if normalized_condition not in auth_tbl.health_conditions:
                self.show_snackbar("This health condition is not supported.")
                return

            # Use normalized key for DB
            condition = normalized_condition

        # Validate numbers
        for value, label in [(age, "Age"), (height, "Height"), (weight, "Weight")]:
            if value and not value.isdigit():
                self.show_snackbar(f"{label} must be a valid number.")
                return

        # 🔥 DETECT CONDITION CHANGE
        condition_changed = (
                old_has_condition != has_condition or
                old_condition != condition
        )

        def confirm_update(instance):
            try:
                # ---------- RECALCULATE BMI ----------
                height_m = float(height) / 100
                weight_val = float(weight)

                new_bmi = round(weight_val / (height_m ** 2), 2)

                # ---------- RECALCULATE DAILY NET CALORIE ----------
                goal_info = auth_tbl.get_user_goal_info(self.user_id)
                goal = normalize_goal(goal_info["Goal"])
                desired_weight = float(goal_info["DesiredWeight"])

                new_daily_goal = auth_tbl.calculate_daily_goal(
                    weight=weight_val,
                    height=float(height),
                    age=int(age),
                    gender=gender.lower(),
                    activity=activity,
                    goal=goal,
                    desired_weight=desired_weight,
                    health_condition=condition or "none"
                )

                # BMI STATUS
                if new_bmi < 18.5:
                    bmi_status = "Underweight"
                elif new_bmi < 25:
                    bmi_status = "Normal"
                elif new_bmi < 30:
                    bmi_status = "Overweight"
                else:
                    bmi_status = "Obese"

                # ---------- UPDATE PROFILE ----------
                sql = """
                    UPDATE data_db
                    SET Username=%s,
                        Fullname=%s,
                        Age=%s,
                        Gender=%s,
                        Height=%s,
                        Weight=%s,
                        ActivityLevel=%s,
                        HasHealthConditions=%s,
                        WhatHealthConditions=%s,
                        BMI=%s,
                        BMIStatus=%s,
                        DailyNetGoal=%s,
                        Updated_at = NOW()
                    WHERE UserId=%s
                """

                auth_tbl.cursor.execute(sql, (
                    username,
                    fullname,
                    age,
                    gender,
                    height,
                    weight,
                    activity,
                    has_condition,
                    condition,
                    new_bmi,
                    bmi_status,
                    round(new_daily_goal),
                    self.user_id
                ))

                auth_tbl.db.commit()

                # 🔥 CLEAR SAVED EXERCISES IF CONDITION CHANGED
                if condition_changed:
                    auth_tbl.clear_user_saved_exercises(self.user_id)
                    self.force_exercise_refresh()

                self.profile_dialog.dismiss()
                self.on_pre_enter()  # 🔁 refresh UI
                self.show_snackbar("Profile updated successfully!")

            except Exception as e:
                auth_tbl.db.rollback()
                print("UPDATE PROFILE ERROR:", e)
                self.show_snackbar("Update failed.")

            self.confirm_dialog.dismiss()

        self.confirm_dialog = MDDialog(
            MDDialogHeadlineText(text="Are you sure?"),
            MDDialogSupportingText(
                text="This will recalculate your daily calorie net goals which will overwrite any custom settings. Would you like to continue?"
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="No"),
                    style="filled", theme_bg_color="Custom", md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.confirm_dialog.dismiss()
                ),
                MDButton(
                    MDButtonText(text="Yes"),
                    style="filled", theme_bg_color="Custom", md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=confirm_update
                ),
                spacing="10dp"
            ),
            auto_dismiss=False
        )
        self.confirm_dialog.open()


    # --- CHANGE PASSWORD ACCOUNT DIALOG ---
    def open_change_password_dialog(self):
        self.generated_otp = ""
        self.otp_fields = []

        if hasattr(self, "timer_event") and self.timer_event:
            self.timer_event.cancel()

        # ---------- EMAIL LABEL ----------
        email_label = MDLabel(
            text="Email",
            halign="left",
            size_hint_x=None,
            width=dp(300),
            pos_hint={"center_x": 0.5},
        )

        # ---------- EMAIL FIELD ----------
        self.email_field = MDTextField(
            hint_text="Email",
            mode="outlined",
            size_hint_x=None,
            width=dp(300),
            pos_hint={"center_x": 0.5},
            radius=[20, 20, 20, 20],
            theme_line_color="Custom",
            line_color_focus=(0.1, 0.7, 0.1, 1),
        )

        self.send_otp_btn = MDButton(
            MDButtonText(text="Verify Email"),
            style="text",
            pos_hint={"right": 1},
        )
        self.send_otp_btn.on_release = self.send_change_password_otp

        # ---------- EMAIL SECTION CONTAINER ----------
        email_container = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),  # space between label, field, button
            size_hint_y=None,
            height=dp(95),  # ⬅ reduce this to move UP
            size_hint_x=None,
            width=dp(320),
            pos_hint={"center_x": 0.5},
        )

        email_container.add_widget(email_label)
        email_container.add_widget(self.email_field)
        email_container.add_widget(self.send_otp_btn)

        # ---------- OTP TITLE ----------
        otp_label = MDLabel(
            text="Enter the 6-digit code sent to your email",
            halign="center",
            font_size="14sp"
        )

        # ---------- OTP BOX ----------
        otp_box = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            size_hint_x=None,
            width=dp(300),
            pos_hint={"center_x": 0.5},
        )

        for _ in range(6):
            tf = MDTextField(
                size_hint=(None, None),
                width=dp(42),
                height=dp(56),
                font_size="22sp",
                halign="center",
                input_filter="int",
                mode="outlined",
                multiline=False,
                radius=[15, 15, 15, 15],
                theme_line_color="Custom",
                line_color_focus=(0.1, 0.7, 0.1, 1),
            )
            tf.bind(text=self.limit_otp_input)
            self.otp_fields.append(tf)
            otp_box.add_widget(tf)

        # ---------- RESEND ----------
        self.resend_text = MDButtonText(text="Resend OTP (300s)")
        self.resend_button = MDButton(
            self.resend_text,
            style="text",
            disabled=True,
            pos_hint={"right": 1},
        )
        self.resend_button.on_release = self.resend_change_password_otp

        # ---------- OTP SECTION CONTAINER ----------
        otp_container = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),  # space between label, field, button
            size_hint_y=None,
            height=dp(150),  # ⬅ reduce this to move UP
            size_hint_x=None,
            width=dp(320),
            pos_hint={"center_x": 0.5},
        )

        otp_container.add_widget(otp_label)
        otp_container.add_widget(otp_box)
        otp_container.add_widget(self.resend_button)

        # ---------- CONTENT ----------
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),
            height=dp(110),
            padding=[dp(20), dp(10), dp(20), dp(10)],
            adaptive_height=True,
        )

        content.add_widget(email_container)
        content.add_widget(otp_container)

        # ---------- BUTTONS ----------
        cancel_btn = MDButton(
            MDButtonText(text="Cancel"),
            style="filled",
            theme_bg_color="Custom",
            md_bg_color=(0.6, 0.8, 0.6, 1),
            radius=[20, 20, 20, 20],
            on_release=lambda x: self.change_pass_dialog.dismiss(),
        )

        verify_btn = MDButton(
            MDButtonText(text="Verify"),
            style="filled",
            theme_bg_color="Custom",
            md_bg_color=(0.1, 0.7, 0.1, 1),
            radius=[20, 20, 20, 20],
            on_release=self.verify_change_password_otp,
        )

        # ---------- DIALOG ----------
        self.change_pass_dialog = MDDialog(
            MDDialogHeadlineText(
                text="Change Password",
                halign="center",
            ),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(
                Widget(size_hint_x=1),
                cancel_btn,
                verify_btn,
                spacing="12dp",
            ),
            auto_dismiss=False,
        )

        self.change_pass_dialog.open()


    def verify_change_password_otp(self, *args):
        entered = "".join(tf.text.strip() for tf in self.otp_fields)

        # ❌ No OTP entered
        if not entered:
            self.show_snackbar("Please enter the OTP.", success=False)
            return

        # ❌ Incomplete OTP
        if len(entered) < 6:
            self.show_snackbar("Please enter the complete 6-digit OTP.", success=False)
            return

        # ❌ OTP expired
        from time import time
        if not self.otp_created_at or (time() - self.otp_created_at) > self.OTP_VALIDITY_SECONDS:
            self.show_snackbar("Incorrect or expired OTP.", success=False)
            return

        # ❌ Incorrect OTP
        if entered != self.generated_otp:
            self.show_snackbar("Incorrect or expired OTP.", success=False)
            return

        # ✅ OTP VALID
        self.change_pass_dialog.dismiss()
        self.open_new_password_dialog()

    def resend_change_password_otp(self, *args):
        self.send_change_password_otp()

    def start_resend_timer(self):
        if hasattr(self, "timer_event") and self.timer_event:
            self.timer_event.cancel()

        self.resend_seconds = 300
        self.resend_button.disabled = True
        self.resend_text.text = f"Resend OTP ({self.resend_seconds}s)"

        self.timer_event = Clock.schedule_interval(self.update_timer, 1)

    def update_timer(self, dt):
        self.resend_seconds -= 1
        if self.resend_seconds > 0:
            self.resend_text.text = f"Resend OTP ({self.resend_seconds}s)"
        else:
            self.resend_button.disabled = False
            self.resend_text.text = "Resend OTP"
            self.timer_event.cancel()

    def limit_otp_input(self, instance, value):
        # force single digit
        if len(value) > 1:
            instance.text = value[-1]

        # auto move to next field
        if value and instance in self.otp_fields:
            idx = self.otp_fields.index(instance)
            if idx < 5:
                self.otp_fields[idx + 1].focus = True

    def send_change_password_otp(self, *args):
        email = self.email_field.text.strip()

        if not email:
            self.show_snackbar("Email is required.", success=False)
            return

        registered_email = auth_tbl.get_email_by_user_id(self.user_id)

        if email != registered_email:
            self.show_snackbar(
                "The email does not match the email on file.",
                success=False
            )
            return

        # ✅ Generate OTP
        from time import time
        from random import randint
        self.generated_otp = str(randint(100000, 999999))
        self.otp_created_at = time()  # ⏱ SAVE TIME

        print("DEBUG OTP:", self.generated_otp)

        if send_otp(email, self.generated_otp):
            self.show_snackbar("OTP sent successfully.", success=True)

            # ✅ DISABLE SEND BUTTON AFTER FIRST SUCCESS
            self.send_otp_btn.disabled = True

            self.start_resend_timer()
        else:
            self.show_snackbar("Failed to send OTP.", success=False)

    # open_new_password_dialog
    def toggle_password_visibility(self, field, icon_btn):
        field.password = not field.password
        icon_btn.icon = "eye" if not field.password else "eye-off"

    def password_field_with_eye(self):
        field = MDTextField(
            password=True,
            password_mask="•",
            mode="outlined",
            size_hint_x=1,
            height=dp(48),
            radius=[20, 20, 20, 20],
            theme_line_color="Custom",
            line_color_focus=(0.1, 0.7, 0.1, 1),
        )

        eye_btn = MDIconButton(
            icon="eye-off",
            size_hint=(None, None),
            size=(dp(32), dp(32)),
            pos_hint={"right": 0.92, "center_y": 0.5},
            on_release=lambda x: self.toggle_password_visibility(field, x),
        )

        row = FloatLayout(
            size_hint_x=None,
            width=dp(250),  # ✅ fits inside dialog
            height=dp(48),
        )

        field.pos_hint = {"x": 0, "center_y": 0.5}

        row.add_widget(field)
        row.add_widget(eye_btn)

        return field, row

    def open_new_password_dialog(self):
        # ---------- LABELS ----------
        def label(text):
            return MDLabel(
                text=text,
                size_hint_x=None,
                width=dp(250),
                size_hint_y=None,
                height=dp(18),  # ✅ proper label height
                halign="left",
                valign="bottom",
            )

        # ---------- PASSWORD FIELDS ----------
        self.old_password_field, old_row = self.password_field_with_eye()
        self.new_password_field, new_row = self.password_field_with_eye()
        self.confirm_password_field, confirm_row = self.password_field_with_eye()

        def field_group(lbl, row):
            box = MDBoxLayout(
                orientation="vertical",
                spacing=dp(4),  # ✅ tight label → field spacing
                size_hint_y=None,
            )
            box.add_widget(label(lbl))
            box.add_widget(row)
            box.height = dp(66)  # ✅ consistent group height
            return box
        # ---------- CONTENT ----------
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),  # ✅ space BETWEEN groups
            padding=(dp(20), dp(12), dp(20), dp(4)),
            size_hint_y=None,
            height=dp(240),  # balanced dialog height
            size_hint_x=None,
            width=dp(320),
            pos_hint={"center_x": 0.5},
        )

        content.add_widget(label("Old Password"))
        content.add_widget(old_row)

        content.add_widget(label("New Password"))
        content.add_widget(new_row)

        content.add_widget(label("Confirm New Password"))
        content.add_widget(confirm_row)

        # ---------- BUTTONS ----------
        cancel_btn = MDButton(
            MDButtonText(text="Cancel"),
            style="filled",
            theme_bg_color="Custom",
            md_bg_color=(0.6, 0.8, 0.6, 1),
            radius=[20, 20, 20, 20],
            on_release=lambda x: self.new_password_dialog.dismiss(),
        )

        confirm_btn = MDButton(
            MDButtonText(text="Confirm"),
            style="filled",
            theme_bg_color="Custom",
            md_bg_color=(0.1, 0.7, 0.1, 1),
            radius=[20, 20, 20, 20],
            on_release=self.confirm_new_password,
        )

        # ---------- DIALOG ----------
        self.new_password_dialog = MDDialog(
            MDDialogHeadlineText(
                text="Create New Password",
                halign="center",
            ),
            MDDialogContentContainer(content),
            MDDialogButtonContainer(
                Widget(size_hint_x=1),
                cancel_btn,
                confirm_btn,
                spacing="12dp",
            ),
            auto_dismiss=False,
        )

        self.new_password_dialog.open()

    def confirm_new_password(self, *args):
        old_pw = self.old_password_field.text.strip()
        new_pw = self.new_password_field.text.strip()
        confirm_pw = self.confirm_password_field.text.strip()

        if not old_pw or not new_pw or not confirm_pw:
            self.show_snackbar("All fields are required.", success=False)
            return

        # 🔐 verify old password
        if not auth_tbl.verify_user_password(self.user_id, old_pw):
            self.show_snackbar("Old password is incorrect.", success=False)
            return

        # ❌ passwords mismatch
        if new_pw != confirm_pw:
            self.show_snackbar("New passwords do not match.", success=False)
            return

        # ❌ same as old
        if old_pw == new_pw:
            self.show_snackbar(
                "New password must be different from old password.",
                success=False,
            )
            return

        # 🔄 update password
        if auth_tbl.update_password(self.user_id, new_pw):
            self.new_password_dialog.dismiss()
            self.show_snackbar("Password updated successfully.", success=True)
        else:
            self.show_snackbar("Failed to update password.", success=False)

    def reset(self):
        self.user_id = None

        if "profile_img" in self.ids:
            img = self.ids.profile_img
            img.texture = None
            img.source = "profile_default.png"
            img.reload()

    # LOGOUT
    def logout(self):
        app = MDApp.get_running_app()

        # ❌ clear memory
        app.current_user_id = None
        app.current_user_name = None

        # ❌ clear persistent session
        if app.store.exists("user"):
            app.store.delete("user")

        # reset app UI
        app.reset_all()


class FAQSScreen(MDScreen):
    pass


class PostTemplate(MDCard):
    def reset(self):
        img = self.ids.p_image
        img.texture = None
        img.source = ""
        img.opacity = 0
        img.height = 0
        img.size_hint_y = None


HIGHLIGHT_SOFT = "#FFE082" #STAY
HIGHLIGHT_ACTIVE = "#F60707" #BUMABABA

class AIFitnessBuddyScreen(MDScreen):
    user_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_chat_id = None

        # 🔍 WORD-BASED SEARCH STATE
        self.search_query = ""
        self.visible_pairs = []  # list of (user_bubble, ai_bubble)
        self.search_results = []  # list of {"bubble", "start", "end"}
        self.search_index = 0
        self.search_counter = None
        self.is_searching = False

    def highlight_text(self, text, query, active_range=None):
        if not query:
            return text

        import re
        pattern = re.compile(rf"\b{re.escape(query)}\b", re.IGNORECASE)

        result = ""
        last = 0

        for match in pattern.finditer(text):
            start, end = match.span()
            result += text[last:start]

            if active_range == (start, end):
                result += f"[color={HIGHLIGHT_ACTIVE}]{text[start:end]}[/color]"
            else:
                result += f"[color={HIGHLIGHT_SOFT}]{text[start:end]}[/color]"

            last = end

        result += text[last:]
        return result

    # SCREEN ENTER
    def on_enter(self):
        app = MDApp.get_running_app()

        if getattr(app, "current_user_id", None) is None:
            print("❌ No user logged in")
            return

        # 🔥 HARD RESET (chat + search)
        self.current_chat_id = None
        self.ids.chat_container.clear_widgets()
        self.reset_search_state()

        self.start_new_chat()

    def on_leave(self):
        # 🔥 Reset search when leaving the screen
        self.reset_search_state()

    # -----------------------------
    # NEW CHAT
    # -----------------------------

    def start_new_chat(self):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)
        if not user_id:
            return

        # Always create or load the single chat
        self.current_chat_id = auth_tbl.get_or_create_chat(user_id)
        self.ids.chat_container.clear_widgets()
        self.load_chat(self.current_chat_id)

    # -----------------------------
    # LOAD CHAT
    # -----------------------------
    def adjust_input_height(self, textfield):
        def update_height(dt):
            max_height = dp(120)   # Maximum input box height
            min_height = dp(52)    # Minimum input box height
            bottom_padding = dp(8)  # Space above bottom nav

            # Measure text height using CoreLabel (takes wrapping into account)
            label = CoreLabel(
                text=textfield.text,
                font_size=textfield.font_size,
                width=textfield.width,
                halign=textfield.halign
            )
            label.refresh()
            text_height = label.texture.size[1] + dp(12)  # Add padding

            # Compute new height within limits
            new_height = min(max(min_height, text_height), max_height)

            # Only animate if the height actually changes (prevents bouncing)
            if not hasattr(textfield, '_prev_height'):
                textfield._prev_height = textfield.height

            if abs(textfield._prev_height - new_height) > 1:
                Animation(height=new_height, d=0.05).start(textfield)

                if textfield.parent:
                    Animation(height=new_height + bottom_padding,
                              d=0.05).start(textfield.parent)

                textfield._prev_height = new_height

            # Enable scrolling if text exceeds max_height
            textfield.do_scroll_y = text_height > max_height
            textfield.scroll_y = 0 if text_height > max_height else 1

        # Schedule on next frame
        Clock.schedule_once(update_height, 0)

    # SIMPLE AI LOGIC
    # -----------------------------

    def generate_response(self, message):
        msg = message.lower()

        if any(w in msg for w in ("workout", "exercise", "train")):
            return "I can help you with workouts. Tell me your fitness goal!"
        if any(w in msg for w in ("calorie", "food", "diet")):
            return "You can track calories in the Calorie Counter."
        if any(w in msg for w in ("hi", "hello", "hey")):
            return "Hello! I'm your AI Fitness Buddy!"

        return "I can help with workouts, nutrition, and navigating the app."

    # DELETE CHAT
    def delete_all_messages(self):
        if not self.current_chat_id:
            return

        success = auth_tbl.delete_all_messages(self.current_chat_id)
        if success:
            self.ids.chat_container.clear_widgets()

            # 🔥 SHOW BUTTON WHEN EMPTY
            self.update_empty_chat_ui()

            self.show_msg("Conversation deleted successfully")

    def delete_user_message_and_response(self, user_message_id):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)

        if not self.current_chat_id or not user_id:
            return

        messages = auth_tbl.get_chat_messages(self.current_chat_id, user_id)

        user_index = next(
            (i for i, m in enumerate(messages)
             if m["message_id"] == user_message_id and m["role"] == "user"),
            None
        )
        if user_index is None:
            return

        auth_tbl.delete_message(user_message_id)

        if user_index + 1 < len(messages):
            next_msg = messages[user_index + 1]
            if next_msg["role"] == "assistant":
                auth_tbl.delete_message(next_msg["message_id"])

        # Reload chat after deletion
        self.load_chat(self.current_chat_id)

        # --- after deleting user msg + assistant msg in DB ---

        # If currently searching, refresh search results in REAL TIME
        if self.is_searching and self.search_query:
            self.refresh_search_if_active()
        else:
            self.load_chat(self.current_chat_id)
            self.show_msg("Message deleted successfully")

    def show_delete_message_dialog(self, message_id):

        dialog = MDDialog(
            MDDialogHeadlineText(text="Delete Message?"),
            MDDialogSupportingText(
                text="This will delete this message and its AI response. This action cannot be undone."
            ),
            MDDialogButtonContainer(
                Widget(),

                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: dialog.dismiss()
                ),

                MDButton(
                    MDButtonText(text="Delete"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: (
                        self.delete_user_message_and_response(message_id),
                        dialog.dismiss()
                    )
                ),

                spacing="10"
            )
        )

        dialog.open()

    # ADD this method for search dialog
    def show_search_dialog(self):
        search_field = MDTextField(
            hint_text="Search messages...",
            mode="outlined"
        )

        def search_action(*args):
            query = search_field.text.strip()
            if query:
                self.perform_search(query)
            dialog.dismiss()

        dialog = MDDialog(
            MDDialogHeadlineText(text="Search Messages"),
            MDDialogContentContainer(
                search_field,
                orientation="vertical",
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: dialog.dismiss()
                ),
                MDButton(
                    MDButtonText(text="Search"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    radius=[20, 20, 20, 20],
                    on_release=search_action
                ),
                spacing="10"
            )
        )
        dialog.open()

    def perform_search(self, query):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)

        if not self.current_chat_id or not user_id or not query.strip():
            return

        import re
        pattern = re.compile(rf"\b{re.escape(query)}\b", re.IGNORECASE)

        messages = auth_tbl.get_chat_messages(self.current_chat_id, user_id)

        self.ids.chat_container.clear_widgets()
        self.search_results = []
        self.search_index = 0
        self.search_query = query
        self.is_searching = True

        for msg in messages:
            bubble = (
                UserBubble(
                    message_text=msg["content"],
                    message_id=msg["message_id"],
                    original_text=msg["content"]
                )
                if msg["role"] == "user"
                else AIBubble(
                    message_text=msg["content"],
                    message_id=msg["message_id"],
                    original_text=msg["content"]
                )
            )

            self.ids.chat_container.add_widget(bubble)

            for match in pattern.finditer(msg["content"]):
                self.search_results.append({
                    "bubble": bubble,
                    "start": match.start(),
                    "end": match.end()
                })

        if not self.search_results:
            # Reset search UI cleanly
            self.reset_search_state()

            # Reload chat without highlights
            self.load_chat(self.current_chat_id)

            self.show_msg(f"No results found for '{query}'")
            return

        self.build_search_bar()
        self.update_active_word()

    def refresh_search_if_active(self):
        """
        Re-run the current search query against the latest DB state.
        If there are no results, clear search UI and show message.
        """
        if not self.search_query:
            return

        query = self.search_query  # keep a stable copy
        self.perform_search(query)

        # perform_search() will set self.search_results
        if not self.search_results:
            # Clear search UI + show normal chat view
            self.reset_search_state()
            self.load_chat(self.current_chat_id)
            self.show_msg(f"No results found for '{query}'")

    def update_active_word(self):
        if not self.search_results:
            return

        active_item = self.search_results[self.search_index]
        active_bubble = active_item["bubble"]
        active_range = (active_item["start"], active_item["end"])

        rendered = set()

        # 🔹 Update highlights (ONE redraw per bubble)
        for item in self.search_results:
            bubble = item["bubble"]

            if bubble in rendered:
                continue
            rendered.add(bubble)

            bubble.message_text = self.highlight_text(
                bubble.original_text,
                self.search_query,
                active_range if bubble is active_bubble else None
            )

        self.search_counter.text = f"{self.search_index + 1} / {len(self.search_results)}"

        # 🔹 Scroll AFTER layout settles
        Clock.schedule_once(
            lambda dt: self._scroll_after_layout(active_bubble),
            0
        )

    def _scroll_after_layout(self, bubble):
        container = self.ids.chat_container
        container.do_layout()

        Clock.schedule_once(
            lambda dt: self.scroll_to_widget(bubble),
            0
        )

    def build_search_bar(self):
        self.ids.search_bar.clear_widgets()
        self.ids.search_bar.height = dp(80)
        self.ids.search_bar.opacity = 1

        # ---------- HEADER ----------
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            padding=[15, 5],
            spacing=10
        )

        label = MDLabel(
            text=f"Found {len(self.search_results)} result(s) with '{self.search_query}'",
            halign="left",
        )

        self.search_counter = MDLabel(
            text=f"{self.search_index + 1} / {len(self.search_results)}",
            halign="center",
        )

        close_btn = MDButton(
            MDButtonText(text="Clear Search"),
            style="text",
            on_release=lambda x: self.clear_search()
        )

        header.add_widget(label)
        header.add_widget(close_btn)

        # ---------- NAV ----------
        nav = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            padding=[15, 0],
            spacing=10
        )

        up_btn = MDIconButton(
            icon="chevron-up",
            on_release=lambda x: self.navigate_search(-1)
        )

        down_btn = MDIconButton(
            icon="chevron-down",
            on_release=lambda x: self.navigate_search(1)
        )

        self.search_counter = MDLabel(
            text=f"Found {len(self.search_results)} result(s) with '{self.search_query}'",
            halign="center",
            size_hint_x=1,
            theme_text_color="Custom",
            text_color=(0.3, 0.3, 0.3, 1)
        )

        nav.add_widget(up_btn)
        nav.add_widget(self.search_counter)
        nav.add_widget(down_btn)

        self.ids.search_bar.add_widget(header)
        self.ids.search_bar.add_widget(nav)

    def update_active_highlight(self):
        for i, (bubble, start, end) in enumerate(self.search_matches):
            active_range = (start, end) if i == self.search_index else None

            bubble.message_text = self.highlight_text(
                bubble.original_text,
                self.search_query,
                active_range=active_range
            )

        self.search_counter.text = (
            f"{self.search_index + 1} / {len(self.search_matches)}"
        )

        # Auto scroll to active word
        Clock.schedule_once(
            lambda dt: self.scroll_to_widget(
                self.search_matches[self.search_index][0]
            ),
            0
        )

    def navigate_search(self, direction):
        if not self.search_results:
            return

        self.search_index = (self.search_index + direction) % len(self.search_results)
        self.update_active_word()

    def collect_search_results(self, query):
        self.search_results.clear()
        self.search_index = 0

        for bubble in self.visible_pairs:
            text = bubble.text
            ranges = []

            import re
            pattern = re.compile(rf"\b{re.escape(query)}\b", re.IGNORECASE)

            for m in pattern.finditer(text):
                ranges.append(m.span())

            if ranges:
                self.search_results.append({
                    "bubble": bubble,
                    "ranges": ranges
                })

        self.update_highlights()

    def next_match(self):
        matches = self.get_flat_matches()
        if not matches:
            return

        self.search_index = (self.search_index + 1) % len(matches)
        self.update_highlights()

    def prev_match(self):
        matches = self.get_flat_matches()
        if not matches:
            return

        self.search_index = (self.search_index - 1) % len(matches)
        self.update_highlights()

    def update_highlights(self):
        matches = self.get_flat_matches()
        active = matches[self.search_index] if matches else None

        for item in self.search_results:
            bubble = item["bubble"]
            original_text = bubble.original_text  # IMPORTANT: store raw text

            active_range = None
            if active and active[0] == bubble:
                active_range = active[1]

            bubble.text = self.highlight_text(
                original_text,
                self.search_query,
                active_range=active_range
            )

    def get_flat_matches(self):
        flat = []
        for item in self.search_results:
            for r in item["ranges"]:
                flat.append((item["bubble"], r))
        return flat

    def scroll_to_widget(self, widget):
        scroll = self.ids.chat_scroll

        if widget:
            scroll.scroll_to(widget, padding=dp(20), animate=False)

    def clear_search(self):
        self.reset_search_state()

        if self.current_chat_id:
            self.load_chat(self.current_chat_id)

    # ADD this method for delete all dialog
    def show_delete_all_dialog(self):
        dialog = MDDialog(
            MDDialogHeadlineText(text="Delete All Messages?"),
            MDDialogSupportingText(
                text="This will delete all messages in this chat. This action cannot be undone."
            ),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: dialog.dismiss()
                ),
                MDButton(
                    MDButtonText(text="Delete All"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    radius=[20, 20, 20, 20],
                    on_release=lambda x: (
                        self.delete_all_messages(), dialog.dismiss())
                ),
                spacing="10"
            )
        )
        dialog.open()

    def update_empty_chat_ui(self):
        has_messages = len(self.ids.chat_container.children) > 0

        if has_messages:
            # Hide empty-chat button / UI
            if "quick_nav" in self.ids:
                self.ids.quick_nav.height = 0
                self.ids.quick_nav.opacity = 0

            if "welcome_box" in self.ids:
                self.ids.welcome_box.height = 0
                self.ids.welcome_box.opacity = 0
        else:
            # Show empty-chat button / UI
            if "quick_nav" in self.ids:
                self.ids.quick_nav.height = dp(260)
                self.ids.quick_nav.opacity = 1

            if "welcome_box" in self.ids:
                self.ids.welcome_box.height = dp(180)
                self.ids.welcome_box.opacity = 1



    # UPDATE load_chat to pass message_id
    def load_chat(self, chat_id):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)

        if not chat_id or not user_id:
            return

        # 🔒 SECURITY CHECK — chat ownership
        if not auth_tbl.chat_belongs_to_user(chat_id, user_id):
            print("🚨 Blocked unauthorized chat access")
            return

        self.current_chat_id = chat_id
        self.ids.chat_container.clear_widgets()

        messages = auth_tbl.get_chat_messages(chat_id, user_id)

        if messages:
            self.ids.welcome_box.height = 0
            self.ids.welcome_box.opacity = 0

            self.ids.quick_nav.height = 0
            self.ids.quick_nav.opacity = 0
        else:
            self.ids.welcome_box.height = dp(180)
            self.ids.welcome_box.opacity = 1

            self.ids.quick_nav.height = dp(260)
            self.ids.quick_nav.opacity = 1

        for msg in messages:
            if msg["role"] == "user":
                self.add_user_bubble(msg["content"], msg["message_id"])
            else:
                self.add_ai_bubble(msg["content"], msg["message_id"])

    # ADD THIS - SEND MESSAGE METHOD (you're missing this!)
    def send_message(self):

        text = self.ids.message_input.text.strip()
        if not text:
            return  # Ignore empty messages

        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)
        if not user_id:
            print("❌ No user logged in")
            return

        # If currently searching, clear search first
        if self.is_searching:
            self.clear_search()

        # Ensure chat exists
        if not self.current_chat_id:
            self.current_chat_id = auth_tbl.get_or_create_chat(user_id)
            if not self.current_chat_id:
                print("❌ Failed to create or get chat")
                return

        if "quick_nav" in self.ids:
            self.ids.quick_nav.height = 0
            self.ids.quick_nav.opacity = 0

        # Clear input box immediately
        self.ids.message_input.text = ""

        # Save user message in DB
        user_message_id = auth_tbl.save_message(
            self.current_chat_id, "user", text
        )
        if user_message_id:
            self.add_user_bubble(text, user_message_id)

        # Hide welcome box
        if "welcome_box" in self.ids:
            self.ids.welcome_box.height = 0
            self.ids.welcome_box.opacity = 0

        # Get AI response safely
        self.get_ai_response(text)

        # Schedule scroll to bottom (slightly delayed to let UI update)
        Clock.schedule_once(self.scroll_to_bottom, 0.1)

   # ADD THIS - SCROLL TO BOTTOM (you're missing this!)

    def add_user_bubble(self, text, message_id=None):
        bubble = UserBubble(message_text=text, message_id=message_id or 0)
        self.ids.chat_container.add_widget(bubble)

        # Update height after render
        def update_height(dt):
            bubble.height = bubble.ids.bubble_container.height + dp(10)
            self.ids.chat_container.height = sum(
                [w.height + self.ids.chat_container.spacing for w in self.ids.chat_container.children])
            self.scroll_to_bottom()
        Clock.schedule_once(update_height, 0)

    def add_ai_bubble(self, text, message_id=None):
        bubble = AIBubble(message_text=text, message_id=message_id or 0)
        self.ids.chat_container.add_widget(bubble)

        def update_height(dt):
            bubble.height = bubble.ids.bubble_container.height + dp(10)
            self.ids.chat_container.height = sum(
                [w.height + self.ids.chat_container.spacing for w in self.ids.chat_container.children])
            self.scroll_to_bottom()
        Clock.schedule_once(update_height, 0)

    def get_ai_response(self, message):
        """
        Process AI response safely in a separate thread.
        Handles DB thread-safety, AI errors, user login, and search mode.
        """
        user_id = getattr(MDApp.get_running_app(), "current_user_id", None)
        if not user_id:
            print("❌ No logged-in user; cannot send AI response")
            return

        if self.is_searching:
            print("⚠ Skipping AI bubble because search is active")
            return

        if not self.current_chat_id:
            print("❌ No current chat; cannot save AI response")
            return

        def worker():
            try:
                # Call AI logic once
                response = process_message(message, user_id)
            except Exception as e:
                response = "Oops! Something went wrong. Try again."
                print(f"❌ process_message error: {e}")
                import traceback
                traceback.print_exc()

            try:
                # Save AI response safely in DB
                ai_message_id = auth_tbl.save_message_thread_safe(
                    self.current_chat_id, "assistant", response)

                # Update UI on main thread
                Clock.schedule_once(
                    lambda dt: self.add_ai_bubble(response, ai_message_id))

            except Exception as e:
                print(f"❌ AI response thread failed: {e}")
                import traceback
                traceback.print_exc()

        Thread(target=worker, daemon=True).start()

    def scroll_to_bottom(self, *args):
        if not self.is_searching:
            self.ids.chat_scroll.scroll_y = 0

    def show_msg(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp"
            ),
            duration=2,
            size_hint=(0.9, None),
            height="50dp",
            pos_hint={"center_x": 0.5, "y": 0.02},
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

    def go_to_dashboard(self):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)

        screen = self.manager.get_screen("dashboard_screen")
        screen.set_user_id(user_id)
        self.manager.current = "dashboard_screen"

    def go_to_calorie_counter(self):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)

        screen = self.manager.get_screen("calorie_counter_screen")
        screen.set_user_id(user_id)
        self.manager.current = "calorie_counter_screen"

    def go_to_activity_log(self):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)

        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(user_id)
        self.manager.current = "food_log_screen"

    def go_to_wellness_hub(self):
        app = MDApp.get_running_app()
        user_id = getattr(app, "current_user_id", None)

        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(user_id)
        self.manager.current = "exercise_hub"



    def go_to_article_hub(self):
        screen = self.manager.get_screen("article_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("article_hub")

    def go_to_exercise_hub(self):
        screen = self.manager.get_screen("exercise_hub")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("exercise_hub")

    def go_to_food_log(self):
        screen = self.manager.get_screen("food_log_screen")
        screen.set_user_id(self.user_id)
        self.manager.instant_switch("food_log_screen")

    def go_to_article(self):
        screen = self.manager.get_screen("article_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("article_log_screen")

    def go_to_workout(self):
        screen = self.manager.get_screen("workout_log_screen")
        screen.set_user_id(self.user_id)  # pass user_id
        self.manager.instant_switch("workout_log_screen")

    def set_user_id(self, user_id):
        self.user_id = user_id

    def receive_user_id(self, user_id):
        self.user_id = user_id

        if hasattr(self, "load_user_data"):
            self.load_user_data(user_id)

    def go_back(self):
        self.manager.current = "dashboard_screen"  # change to your actual screen name

    def reset_search_state(self):
        self.is_searching = False
        self.search_query = ""
        self.search_results = []
        self.search_index = 0
        self.search_counter = None

        if "search_bar" in self.ids:
            self.ids.search_bar.clear_widgets()
            self.ids.search_bar.height = 0
            self.ids.search_bar.opacity = 0


class UserBubble(MDBoxLayout):
    message_text = StringProperty("")
    message_id = NumericProperty(0)
    original_text = StringProperty("")


class AIBubble(MDBoxLayout):
    message_text = StringProperty("")
    message_id = NumericProperty(0)
    original_text = StringProperty("")




#Admin
import hashlib
import os
import binascii
from kivy.app import App
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar, MDSnackbarText


class admin_loginScreen(MDScreen):

    # 🔐 ADMIN CREDENTIALS (SECURE)
    ADMIN_USERNAME = "admin"

    # Generated ONCE using PBKDF2
    ADMIN_SALT = "f675611831122110fca1643cf7c34e8f"
    ADMIN_PASSWORD_HASH = "42ea24c4ebd58496b3bfed5315637ec5b51f190b84b0eca2b83ee877afabec0f"

    ITERATIONS = 200_000

    # -----------------------------
    # 🔐 HASH UTILITIES
    # -----------------------------
    def verify_password(self, password_input):
        salt = binascii.unhexlify(self.ADMIN_SALT)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password_input.encode("utf-8"),
            salt,
            self.ITERATIONS
        )
        return binascii.hexlify(pwd_hash).decode() == self.ADMIN_PASSWORD_HASH

    # -----------------------------
    # UI HELPERS
    # -----------------------------
    def show_msg(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp",
            ),
            duration=2,
            size_hint=(0.9, None),
            height="50dp",
            pos_hint={"center_x": 0.5, "y": 0.02},
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()

    def toggle_password_visibility(self, field, icon_btn):
        field.password = not field.password
        icon_btn.icon = "eye" if not field.password else "eye-off"

    def on_pre_enter(self):
        self.ids.username_field.text = ""
        self.ids.password_field.text = ""
        self.ids.password_field.password = True
        self.ids.login_eye_icon.icon = "eye-off"

    # -----------------------------
    # 🔐 ADMIN LOGIN
    # -----------------------------
    def login_admin(self):
        username = self.ids.username_field.text.strip()
        password = self.ids.password_field.text.strip()

        # 🔴 Empty fields
        if not username and not password:
            self.show_msg("Please enter username and password")
            return

        if not username:
            self.show_msg("Username is required")
            return

        if not password:
            self.show_msg("Password is required")
            return

        # 🔐 Username check
        if username != self.ADMIN_USERNAME:
            self.show_msg("Incorrect username")
            return

        # 🔐 Password check (HASHED)
        if not self.verify_password(password):
            self.show_msg("Incorrect password")
            return

        # ✅ SUCCESS
        self.show_msg("Admin login successful")

        app = App.get_running_app()
        app.current_user_id = 0
        app.current_user_name = "Admin"

        app.store.put(
            "user",
            id=0,
            name="Admin",
            role="admin",
        )

        self.manager.current = "admin_dashboard_screen"

class AdminDashboardScreen(MDScreen):

    def on_enter(self, *args):
        today = datetime.now()
        formatted_date = today.strftime("%A, %B %d")
        self.ids.date_label.text = formatted_date

    def on_pre_enter(self, *args):
        self.update_active_feedwall_users()
        self.load_feedwall_users_today()

    def update_active_feedwall_users(self):
        count = auth_tbl.get_active_feedwall_users_today()
        self.ids.active_feedwall_label.text = f"Active Feedwall Users: {count}"

    def load_feedwall_users_today(self):
        container = self.ids.feedwall_users_container
        container.clear_widgets()

        users = auth_tbl.get_feedwall_users_today()

        for user in users:
            card = self.build_user_card(user)
            container.add_widget(card)

    def build_user_card(self, user):
        user_id = user["id"]
        name = user["full_name"]

        violations = auth_tbl.get_user_violations(user_id)

        card = MDCard(
            size_hint_y=None,
            height=dp(160),
            radius=[20, 20, 20, 20],
            md_bg_color=(0.9, 0.92, 0.88, 1),
            elevation=0,
            ripple_behavior=False,  # 🔥 IMPORTANT
            focus_behavior=False,  # 🔥 IMPORTANT
        )

        layout = MDBoxLayout(
            orientation="vertical",
            padding=(dp(16), dp(16), dp(8), dp(16)),
            spacing=dp(12),
        )

        # ---------- TOP ROW ----------
        top = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            size_hint_y=None,
            height=dp(50),
        )

        profile = Image(
            size_hint=(None, None),
            size=(dp(45), dp(45)),
            pos_hint={"center_y": 0.5},
        )

        photo = user.get("photo")
        if photo:
            buffer = io.BytesIO(photo)
            profile.texture = CoreImage(buffer, ext="png").texture
        else:
            profile.source = "profile_default.png"

        info = MDBoxLayout(orientation="vertical", spacing=dp(4))

        info.add_widget(
            MDLabel(
                text=name,
                bold=True,
                font_style="Title",
                theme_text_color="Custom",
                text_color=(0, 0, 0, 1),
            )
        )

        violations = auth_tbl.get_user_violations(user_id)

        info.add_widget(
            MDLabel(
                text=f"Violations: {violations}",
                font_style="Body",
                theme_text_color="Secondary",
            )
        )

        top.add_widget(profile)
        top.add_widget(info)

        btn_row = MDBoxLayout(
            size_hint_y=None,
            height=dp(48),
        )

        btn = MDButton(
            MDButtonText(text="REVIEW POSTS TODAY"),
            style="outlined",  # or "filled"
            size_hint=(1, None),
            height=dp(48),  # 🔥 BIG HITBOX
            theme_text_color="Custom",
            text_color=(0, 0.5, 0, 1),
            on_release=lambda x: self.open_user_posts_today(user_id),
        )
        btn_row.add_widget(btn)

        layout.add_widget(top)
        layout.add_widget(btn_row)
        card.add_widget(layout)
        return card


    def open_user_posts_today(self, user_id):
        screen = self.manager.get_screen("admin_review_posts_screen")
        screen.set_user(user_id, date.today())  # ✅ FIXED
        self.manager.current = "admin_review_posts_screen"

    def set_user(self, user_id):
        self.user_id = user_id
        self.load_posts_today()

    def load_posts_today(self):
        posts = auth_tbl.get_posts_today_by_user(self.user_id)

    def get_violation_count(self, user_id):
        return auth_tbl.get_total_violations(user_id)


class AdminReviewPostsScreen(MDScreen):
    admin_menu = None
    user_id = None
    selected_date = None

    def set_user(self, user_id, selected_date):
        self.user_id = user_id
        self.selected_date = selected_date

    def load_header(self, user_id):
        fullname = auth_tbl.get_user_fullname(user_id)
        if fullname:
            self.ids.header_fullname.text = fullname

        from datetime import datetime
        self.ids.header_date.text = datetime.now().strftime("%A, %B %d")

        photo = auth_tbl.get_user_photo(user_id)
        if photo:
            buffer = io.BytesIO(photo)
            self.ids.header_profile.texture = CoreImage(buffer, ext="png").texture
        else:
            self.ids.header_profile.source = "profile_default.png"

    def _build_and_add_cards(self, posts):
        post_layout = self.ids.post_layout

        for post in posts:
            try:
                card = self.build_post_template(post)

                # 🔥 ADMIN-ONLY: override dropdown behavior
                self._attach_admin_menu(card)

                post_layout.add_widget(card)

            except Exception as e:
                print("POST BUILD ERROR:", e)

    def _attach_admin_menu(self, card):
        container = card.ids.p_menu_button.parent

        # 🔥 REMOVE previous admin buttons (prevents ghost menus)
        for child in container.children[:]:
            if getattr(child, "is_admin_btn", False):
                container.remove_widget(child)

        old_btn = card.ids.p_menu_button
        old_btn.opacity = 0
        old_btn.disabled = True

        from kivymd.uix.button import MDIconButton

        admin_btn = MDIconButton(
            icon="delete",
            theme_icon_color="Custom",
            icon_color=(0.8, 0.2, 0.2, 1),
            pos_hint={"center_y": 0.5},
        )

        admin_btn.is_admin_btn = True
        admin_btn.bind(on_release=lambda *a: self.open_delete_post_dialog(card))

        container.add_widget(admin_btn)

    def _open_admin_menu(self, card):
        if self.admin_menu:
            self.admin_menu.dismiss()
            self.admin_menu = None

        btn = card.ids.p_menu_button

        self.admin_menu = MDDropdownMenu(
            caller=btn,
            items=[
                {
                    "text": "Delete post",
                    "height": dp(36),
                    "on_release": lambda *a: self.open_delete_post_dialog(card),
                }
            ],
            position="bottom",
        )

        self.admin_menu.open()

    def open_delete_post_dialog(self, card):
        if hasattr(self, "post_menu") and self.post_menu:
            self.post_menu.dismiss()

        if hasattr(self, "delete_post_dialog") and self.delete_post_dialog:
            self.delete_post_dialog.dismiss()
            self.delete_post_dialog = None

        self.delete_post_dialog = MDDialog(
            MDDialogHeadlineText(text="Delete post?"),

            MDDialogContentContainer(
                MDBoxLayout(
                    MDLabel(
                        text="This will add 1 violation to the user.",
                        halign="center",
                        theme_text_color="Secondary",
                    ),

                    MDBoxLayout(size_hint_y=None, height=dp(16)),
                    MDBoxLayout(size_hint_y=None, height=dp(8)),

                    MDBoxLayout(
                        MDButton(
                            MDButtonText(text="Cancel"),
                            style="outlined",
                            on_release=lambda *a: self.delete_post_dialog.dismiss(),
                        ),
                        MDButton(
                            MDButtonText(text="Delete"),
                            style="filled",
                            theme_bg_color="Custom",
                            md_bg_color=(0.1, 0.7, 0.1, 1),
                            on_release=lambda *a: self._confirm_and_delete(card),
                        ),

                        orientation="horizontal",
                        spacing=dp(20),
                        adaptive_width=True,
                        pos_hint={"center_x": 0.5},
                    ),

                    orientation="vertical",
                    adaptive_height=True,
                    padding=(dp(24), dp(8), dp(24), dp(16)),
                    spacing=dp(16),
                )
            ),

            auto_dismiss=False,
        )

        self.delete_post_dialog.open()

    def on_leave(self, *args):
        if self.admin_menu:
            self.admin_menu.dismiss()
            self.admin_menu = None

        if hasattr(self, "delete_post_dialog") and self.delete_post_dialog:
            self.delete_post_dialog.dismiss()
            self.delete_post_dialog = None

    def _confirm_and_delete(self, card):
        self.delete_post_dialog.dismiss()

        post_id = card.post_id
        user_id = card.user_id

        # 1️⃣ Hard delete post
        auth_tbl.delete_post(post_id)

        # 2️⃣ Increment violation + auto-deactivate if needed
        violations = auth_tbl.increment_user_violation(user_id)

        # 3️⃣ SET LOGIN NOTICE FOR USER
        notice = (
            "[color=#ff3333][b]Your post was deleted[/b][/color] "
            "due to a violation."
        )

        if violations == 4:
            notice = (
                "[color=#ff3333][b]FINAL WARNING[/b][/color]\n"
                "One more violation and your account will be deactivated."
            )
        elif violations >= 5:
            notice = (
                "[color=#ff3333][b]ACCOUNT DEACTIVATED[/b][/color]\n"
                "Due to repeated violations."
            )

        auth_tbl.set_login_notice(user_id, notice)

        # 4️⃣ Remove from UI
        if card.parent:
            self.ids.post_layout.remove_widget(card)

        # 5️⃣ ADMIN SUCCESS PROMPT
        from kivy.app import App
        App.get_running_app().show_edit_snackbar(
            "Post deleted successfully"
        )

        print(f"✅ Post deleted. User {user_id} now has {violations} violations")

    def build_post_template(self, post):
        from kivy.factory import Factory
        card = Factory.PostTemplate()
        card.post_id = post["PostId"]
        card.user_id = post["UserId"]

        card.ids.p_username.text = post["Fullname"]
        created = post.get("Created_at") or post.get("Created_At")

        if not created:
            card.ids.p_time.text = "—"
        else:
            card.ids.p_time.text = self.format_time(created)

        card.ids.p_text.text = post.get("PostText") or ""

        if post["Audience"] == "Public":
            card.ids.p_audience_icon.icon = "earth"
        else:
            card.ids.p_audience_icon.icon = "lock"

        if post["Photo"]:
            card.ids.p_user_img.texture = CoreImage(
                io.BytesIO(post["Photo"]), ext="png"
            ).texture
        else:
            card.ids.p_user_img.source = "profile_default.png"

        if post["PostImage"]:
            card.ids.p_image.texture = CoreImage(
                io.BytesIO(post["PostImage"]), ext="png"
            ).texture
            card.ids.p_image.height = dp(180)
        else:
            card.ids.p_image.height = 0

        # ADMIN VIEW: menu always visible
        card.ids.p_menu_button.opacity = 1
        card.ids.p_menu_button.disabled = False

        return card

    def format_time(self, dt):
        from datetime import datetime, timedelta
        now = datetime.now()
        diff = now - dt

        if diff < timedelta(minutes=1):
            return "Just now"
        if diff < timedelta(hours=1):
            return f"{diff.seconds // 60}m"
        if diff < timedelta(days=1):
            return f"{diff.seconds // 3600}h"
        if diff < timedelta(days=2):
            return "Yesterday"
        if diff < timedelta(days=7):
            return f"{diff.days}d"
        return dt.strftime("%b %d, %Y")

    # def load_posts(self):
    #     self.ids.post_layout.clear_widgets()
    #
    #     posts = auth_tbl.get_posts_today_by_user(self.user_id)
    #
    #     print("TODAY POSTS COUNT:", len(posts))
    #
    #     for i, post in enumerate(posts):
    #         print(f"POST {i} KEYS:", post.keys())
    #         print(f"POST {i} DATA:", post)
    #
    #     self._build_and_add_cards(posts)

    def load_posts(self):
        self.ids.post_layout.clear_widgets()

        posts = auth_tbl.get_posts_by_user_and_date(
            self.user_id,
            self.selected_date
        )

        self._build_and_add_cards(posts)

    def on_pre_enter(self, *args):
        if not self.user_id:
            print("❌ AdminReview entered without user_id")
            return

        self.load_header(self.user_id)
        self.load_posts()

    def go_back(self):
        # admin flow
        self.manager.current = "admin_dashboard_screen"


class ManageActiveAccountScreen(MDScreen):
    def on_enter(self):
        auth_tbl.auto_deactivate_inactive_accounts()
        self.load_active_accounts()

    def load_active_accounts(self):
        accounts = auth_tbl.get_active_accounts()

        account_list = self.ids.active_account_list
        count_label = self.ids.active_count_label
        account_list.clear_widgets()

        for row in accounts:
            card = Factory.ActiveAccountCard()
            card.ids.name.text = row["Fullname"]
            card.ids.email.text = row["Email"]

            last_login = row.get("LastLogin")
            if last_login:
                formatted = last_login.strftime("%B %d, %Y | %I:%M %p")
                card.ids.last_login.text = f"Last Login: {formatted}"
            else:
                card.ids.last_login.text = "Last Login: Never"

            account_list.add_widget(card)

        count_label.text = f"{len(accounts)} ACTIVE ACCOUNT"

    def go_to_ManageActiveAccountScreen(self):
        self.manager.instant_switch("manage_active_account_screen")

    def go_to_ManageViolatorsAccountScreen(self):
        self.manager.instant_switch("manage_violators_account_screen")

    def go_to_ManageDeactivatedAccountScreen(self):
        self.manager.instant_switch("manage_deactivated_account_screen")


class ManageViolatorsAccountScreen(MDScreen):

    def on_enter(self):
        self.load_violators()

    def load_violators(self):
        accounts = auth_tbl.get_violator_users()

        account_list = self.ids.violators_account_list
        count_label = self.ids.violators_count_label

        account_list.clear_widgets()

        for row in accounts:
            card = Factory.ActiveAccountCard()
            card.ids.name.text = row["Fullname"]
            card.ids.email.text = row["Email"]

            violations = row["ViolationCount"]
            card.ids.last_login.text = f"Violations: {violations}"

            account_list.add_widget(card)

        count_label.text = f"{len(accounts)} VIOLATORS"

    def go_to_ManageActiveAccountScreen(self):
        self.manager.instant_switch("manage_active_account_screen")

    def go_to_ManageViolatorsAccountScreen(self):
        self.manager.instant_switch("manage_violators_account_screen")

    def go_to_ManageDeactivatedAccountScreen(self):
        self.manager.instant_switch("manage_deactivated_account_screen")


class ManageDeactivatedAccountScreen(MDScreen):
    def on_enter(self):
        self.load_deactivated_accounts()

    def load_deactivated_accounts(self):
        accounts = auth_tbl.get_deactivated_accounts()

        account_list = self.ids.deactivated_account_list
        count_label = self.ids.deactivated_count_label
        account_list.clear_widgets()

        for row in accounts:
            card = Factory.DeactivatedAccountCard()

            # BASIC INFO
            card.ids.name.text = row.get("Fullname") or ""
            card.ids.email.text = row.get("Email") or ""

            # 🔁 HARD RESET UI STATE (VERY IMPORTANT)
            card.ids.reason.text = ""
            card.ids.reason.text_color = (0, 0, 0, 1)

            card.ids.last_login.text = ""
            card.ids.last_login.height = dp(18)
            card.ids.last_login.size_hint_y = None
            card.ids.last_login.opacity = 1
            card.ids.last_login.disabled = False

            # ---------- SAFE REASON HANDLING ----------
            reason_raw = row.get("DeactivationReason")

            if isinstance(reason_raw, str):
                reason = reason_raw.lower().strip()
            else:
                reason = ""

            # 🚫 VIOLATION → HIDE last login
            if "violation" in reason:
                card.ids.reason.text = "Deactivated due to violations"
                card.ids.reason.text_color = (0.8, 0.1, 0.1, 1)

                card.ids.last_login.text = ""
                card.ids.last_login.height = 0
                card.ids.last_login.opacity = 0
                card.ids.last_login.disabled = True

            # 💤 INACTIVITY → SHOW last login
            else:
                card.ids.reason.text = "Deactivated due to inactive use"
                card.ids.reason.text_color = (0.8, 0.1, 0.1, 1)

                last_login = row.get("LastLogin")
                if last_login:
                    formatted = last_login.strftime("%B %d, %Y | %I:%M %p")
                    card.ids.last_login.text = f"Last Login: {formatted}"
                else:
                    card.ids.last_login.text = "Last Login: Never"

            account_list.add_widget(card)

        count_label.text = f"{len(accounts)} DEACTIVATED ACCOUNT"

    def go_to_ManageActiveAccountScreen(self):
        self.manager.instant_switch("manage_active_account_screen")

    def go_to_ManageViolatorsAccountScreen(self):
        self.manager.instant_switch("manage_violators_account_screen")

    def go_to_ManageDeactivatedAccountScreen(self):
        self.manager.instant_switch("manage_deactivated_account_screen")


def normalize_program_name(value):
    if not value:
        return "normal"

    v = value.strip().lower()

    if v in ("normal",):
        return "normal"

    if v in ("condition", "health condition", "health_condition"):
        return "condition"

    # fallback
    return "normal"

def blob_to_image_path(img_blob):
    from kivy.app import App
    import hashlib, os

    if not img_blob:
        return "exercisepic/default.png"

    if not isinstance(img_blob, (bytes, bytearray)):
        return "exercisepic/default.png"

    # detect extension
    if img_blob.startswith(b"\xff\xd8\xff"):
        ext = ".jpg"
    elif img_blob.startswith(b"\x89PNG"):
        ext = ".png"
    else:
        ext = ".img"

    cache_dir = os.path.join(App.get_running_app().user_data_dir, "exercise_cache")
    os.makedirs(cache_dir, exist_ok=True)

    fname = hashlib.md5(img_blob).hexdigest() + ext
    path = os.path.join(cache_dir, fname)

    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(img_blob)

    return path

def normalize_goal(goal):
    if not goal:
        return goal

    goal = goal.strip().lower().replace(" ", "_")

    return {
        "gain_muscles": "gain_muscle",
        "gain_muscle": "gain_muscle",
        "lose_weight": "lose_weight",
        "gain_weight": "gain_weight",
        "keep_fit": "keep_fit",
    }.get(goal, goal)

def normalize_exercise_name(name: str) -> str:
    return (
        name.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("  ", " ")
        .strip()
    )

def get_exercise_detail(details, normalized_name):

    """
    Safely extract meaning, steps, benefits
    with exact, cleaned, and fuzzy matching
    """

    # 1️⃣ Exact match
    detail = details.get(normalized_name)

    # 2️⃣ Strip side qualifiers
    if not detail:
        cleaned = normalized_name
        for junk in (
            " left & right",
            " left and right",
            " left right",
            " left",
            " right",
        ):
            cleaned = cleaned.replace(junk, "").strip()

        detail = details.get(cleaned)

    # 3️⃣ Fuzzy fallback (CONTAINS match)
    if not detail:
        for key, value in details.items():
            if key in normalized_name or normalized_name in key:
                detail = value
                break

    if not detail:
        return "", "", ""

    meaning = detail.get("meanings") or detail.get("meaning") or ""
    steps = detail.get("steps") or []
    benefits = detail.get("benefits") or []

    if isinstance(steps, str):
        steps = [steps]

    if isinstance(benefits, str):
        benefits = [benefits]

    return (
        str(meaning).strip(),
        "\n".join(s.strip() for s in steps if s),
        "\n".join(b.strip() for b in benefits if b),
    )

def get_exercise_image(image_index, normalized_name):
    """
    Find exercise image with normalization + fallback
    """

    # 1️⃣ Exact match
    path = image_index.get(normalized_name)
    if path:
        return path

    # 2️⃣ Strip side qualifiers
    cleaned = normalized_name
    for junk in (
        " left & right",
        " left and right",
        " left right",
        " left",
        " right",
    ):
        cleaned = cleaned.replace(junk, "").strip()

    path = image_index.get(cleaned)
    if path:
        return path

    # 3️⃣ Fuzzy fallback
    for key, value in image_index.items():
        if key in normalized_name or normalized_name in key:
            return value

    return None


class admin_wellnesshubScreen(MDScreen):
    current_goal = "lose_weight"

    def open_admin_program(self, goal, level):
        screen = self.manager.get_screen("admin_workout_program")
        screen.set_program(goal, level)
        self.manager.instant_switch("admin_workout_program")

    def on_pre_enter(self, *args):
        self.load_goal("lose_weight")

    def load_goal(self, goal_key):
        self.current_goal = goal_key
        self.update_goal_buttons()
        self.populate_programs(goal_key)

    def update_goal_buttons(self):
        for btn in self.ids.goal_buttons.children:
            btn.md_bg_color = (1, 1, 1, 1)
            btn.children[0].text_color = (0, 0.6, 0, 1)

        active = self.ids[f"btn_{self.current_goal}"]
        active.md_bg_color = (0, 0.6, 0, 1)
        active.children[0].text_color = (1, 1, 1, 1)

    def populate_programs(self, goal_key):
        container = self.ids.admin_wellness_container
        container.clear_widgets()

        levels = ["beginner", "intermediate", "advanced"]

        for level in levels:
            db_goal = normalize_goal(goal_key)

            auth_tbl.cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM user_exercises
                WHERE Goal = %s
                  AND Difficulty = %s
                  AND UserId = 0
                  AND (IsDeleted = 0 OR IsDeleted IS NULL)
                """,
                (db_goal, level)
            )

            row = auth_tbl.cursor.fetchone()
            total_workouts = row["total"] if row else 0

            self.add_program_card(
                program_name=f"{goal_key.replace('_', ' ').title()} {level.title()}",
                difficulty=level,
                total_workouts=total_workouts
            )

    def add_program_card(self, program_name, difficulty, total_workouts):
        banner_map = {
            "beginner": "beginner.jpg",
            "intermediate": "intermediate.jpg",
            "advanced": "advanced.jpg"
        }

        quote_map = {
            "beginner": "Consistency beats perfection every time.",
            "intermediate": "Train with purpose. Grow with discipline.",
            "advanced": "Your mindset is your strongest muscle."
        }

        card = MDCard(
            size_hint_y=None,
            height="200dp",
            radius=[20, 20, 20, 20],
            padding=10,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)

        )

        layout = MDBoxLayout(orientation="vertical", spacing=6)

        image_card = MDCard(
            size_hint_y=None,
            height="140dp",
            radius=[20, 20, 20, 20],
            padding=0,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)
        )

        image_card.add_widget(
            FitImage(
                source=banner_map.get(difficulty.lower(), "program_banner.png"),
                keep_ratio=False,
                allow_stretch=True
            )
        )

        layout.add_widget(image_card)

        layout.add_widget(MDLabel(
            text=f"[b]{quote_map.get(difficulty, '')}[/b]",
            markup=True,
            font_size="12sp"
        ))

        layout.add_widget(MDLabel(
            text=f"{difficulty.title()} | {total_workouts} Workouts",
            font_size="12sp"
        ))

        card.add_widget(layout)
        self.ids.admin_wellness_container.add_widget(card)

    def go_to_gainweight(self):
        self.manager.instant_switch("admin_wellnesshub_gainweightsreen")

    def go_to_loseweight(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_keepfit(self):
        self.manager.instant_switch("admin_wellnesshub_keepfitsreen")

    def go_to_gainmuscles(self):
        self.manager.instant_switch("admin_wellnesshub_gainmusclessreen")

    def go_to_adminexercise(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_adminarticles(self):
        self.manager.instant_switch("admin_articles")

class admin_wellnesshub_gainweightScreen(MDScreen):
    current_goal = "gain_weight"

    def open_admin_program(self, goal, level):
        screen = self.manager.get_screen("admin_workout_program")
        screen.set_program(goal, level)
        self.manager.instant_switch("admin_workout_program")

    def on_pre_enter(self, *args):
        self.load_goal("gain_weight")

    def load_goal(self, goal_key):
        self.current_goal = goal_key
        self.update_goal_buttons()
        self.populate_programs(goal_key)

    def update_goal_buttons(self):
        for btn in self.ids.goal_buttons.children:
            btn.md_bg_color = (1, 1, 1, 1)
            btn.children[0].text_color = (0, 0.6, 0, 1)

        active = self.ids[f"btn_{self.current_goal}"]
        active.md_bg_color = (0, 0.6, 0, 1)
        active.children[0].text_color = (1, 1, 1, 1)

    def populate_programs(self, goal_key):
        container = self.ids.admin_wellness_container
        container.clear_widgets()

        levels = ["beginner", "intermediate", "advanced"]

        for level in levels:
            db_goal = normalize_goal(goal_key)

            auth_tbl.cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM user_exercises
                WHERE Goal = %s
                  AND Difficulty = %s

                  AND UserId = 0
                  AND (IsDeleted = 0 OR IsDeleted IS NULL)
                """,
                (db_goal, level)
            )

            row = auth_tbl.cursor.fetchone()
            total_workouts = row["total"] if row else 0

            self.add_program_card(
                program_name=f"{goal_key.replace('_', ' ').title()} {level.title()}",
                difficulty=level,
                total_workouts=total_workouts
            )

    def add_program_card(self, program_name, difficulty, total_workouts):
        banner_map = {
            "beginner": "beginner.jpg",
            "intermediate": "intermediate.jpg",
            "advanced": "advanced.jpg"
        }

        quote_map = {
            "beginner": "Consistency beats perfection every time.",
            "intermediate": "Train with purpose. Grow with discipline.",
            "advanced": "Your mindset is your strongest muscle."
        }

        card = MDCard(
            size_hint_y=None,
            height="200dp",
            radius=[20, 20, 20, 20],
            padding=10,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)
        )

        layout = MDBoxLayout(orientation="vertical", spacing=6)

        image_card = MDCard(
            size_hint_y=None,
            height="140dp",
            radius=[20, 20, 20, 20],
            padding=0,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)
        )

        image_card.add_widget(
            FitImage(
                source=banner_map.get(difficulty.lower(), "program_banner.png"),
                keep_ratio=False,
                allow_stretch=True
            )
        )

        layout.add_widget(image_card)

        layout.add_widget(MDLabel(
            text=f"[b]{quote_map.get(difficulty, '')}[/b]",
            markup=True,
            font_size="12sp"
        ))

        layout.add_widget(MDLabel(
            text=f"{difficulty.title()} | {total_workouts} Workouts",
            font_size="12sp"
        ))

        card.add_widget(layout)
        self.ids.admin_wellness_container.add_widget(card)

    def go_to_adminexercise(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_adminarticles(self):
        self.manager.instant_switch("admin_articles")

    def go_to_gainweight(self):
        self.manager.instant_switch("admin_wellnesshub_gainweightsreen")

    def go_to_loseweight(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_keepfit(self):
        self.manager.instant_switch("admin_wellnesshub_keepfitsreen")

    def go_to_gainmuscles(self):
        self.manager.instant_switch("admin_wellnesshub_gainmusclessreen")

class admin_wellnesshub_keepfitScreen(MDScreen):
    current_goal = "keep_fit"

    def open_admin_program(self, goal, level):
        screen = self.manager.get_screen("admin_workout_program")
        screen.set_program(goal, level)
        self.manager.instant_switch("admin_workout_program")

    def on_pre_enter(self, *args):
        self.load_goal("keep_fit")

    def load_goal(self, goal_key):
        self.current_goal = goal_key
        self.update_goal_buttons()
        self.populate_programs(goal_key)

    def update_goal_buttons(self):
        for btn in self.ids.goal_buttons.children:
            btn.md_bg_color = (1, 1, 1, 1)
            btn.children[0].text_color = (0, 0.6, 0, 1)

        active = self.ids[f"btn_{self.current_goal}"]
        active.md_bg_color = (0, 0.6, 0, 1)
        active.children[0].text_color = (1, 1, 1, 1)

    def populate_programs(self, goal_key):
        container = self.ids.admin_wellness_container
        container.clear_widgets()

        levels = ["beginner", "intermediate", "advanced"]

        for level in levels:
            db_goal = normalize_goal(goal_key)

            auth_tbl.cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM user_exercises
                WHERE Goal = %s
                  AND Difficulty = %s

                  AND UserId = 0
                  AND (IsDeleted = 0 OR IsDeleted IS NULL)
                """,
                (db_goal, level)
            )

            row = auth_tbl.cursor.fetchone()
            total_workouts = row["total"] if row else 0

            self.add_program_card(
                program_name=f"{goal_key.replace('_', ' ').title()} {level.title()}",
                difficulty=level,
                total_workouts=total_workouts
            )

    def add_program_card(self, program_name, difficulty, total_workouts):
        banner_map = {
            "beginner": "beginner.jpg",
            "intermediate": "intermediate.jpg",
            "advanced": "advanced.jpg"
        }

        quote_map = {
            "beginner": "Consistency beats perfection every time.",
            "intermediate": "Train with purpose. Grow with discipline.",
            "advanced": "Your mindset is your strongest muscle."
        }

        card = MDCard(
            size_hint_y=None,
            height="200dp",
            radius=[20, 20, 20, 20],
            padding=10,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)
        )

        layout = MDBoxLayout(orientation="vertical", spacing=6)

        image_card = MDCard(
            size_hint_y=None,
            height="140dp",
            radius=[20, 20, 20, 20],
            padding=0,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)
        )

        image_card.add_widget(
            FitImage(
                source=banner_map.get(difficulty.lower(), "program_banner.png"),
                keep_ratio=False,
                allow_stretch=True
            )
        )

        layout.add_widget(image_card)

        layout.add_widget(MDLabel(
            text=f"[b]{quote_map.get(difficulty, '')}[/b]",
            markup=True,
            font_size="12sp"
        ))

        layout.add_widget(MDLabel(
            text=f"{difficulty.title()} | {total_workouts} Workouts",
            font_size="12sp"
        ))

        card.add_widget(layout)
        self.ids.admin_wellness_container.add_widget(card)

    def go_to_adminexercise(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_adminarticles(self):
        self.manager.instant_switch("admin_articles")

    def go_to_gainweight(self):
        self.manager.instant_switch("admin_wellnesshub_gainweightsreen")

    def go_to_loseweight(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_keepfit(self):
        self.manager.instant_switch("admin_wellnesshub_keepfitsreen")

    def go_to_gainmuscles(self):
        self.manager.instant_switch("admin_wellnesshub_gainmusclessreen")

class admin_wellnesshub_gainmusclesScreen(MDScreen):
    current_goal = "gain_muscles"

    def open_admin_program(self, goal, level):
        screen = self.manager.get_screen("admin_workout_program")
        screen.set_program(goal, level)
        self.manager.instant_switch("admin_workout_program")

    def on_pre_enter(self, *args):
        self.load_goal("gain_muscles")

    def load_goal(self, goal_key):
        self.current_goal = goal_key
        self.update_goal_buttons()
        self.populate_programs(goal_key)

    def update_goal_buttons(self):
        for btn in self.ids.goal_buttons.children:
            btn.md_bg_color = (1, 1, 1, 1)
            btn.children[0].text_color = (0, 0.6, 0, 1)

        active = self.ids[f"btn_{self.current_goal}"]
        active.md_bg_color = (0, 0.6, 0, 1)
        active.children[0].text_color = (1, 1, 1, 1)

    def populate_programs(self, goal_key):
        container = self.ids.admin_wellness_container
        container.clear_widgets()

        levels = ["beginner", "intermediate", "advanced"]

        for level in levels:
            db_goal = normalize_goal(goal_key)

            auth_tbl.cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM user_exercises
                WHERE Goal = %s
                  AND Difficulty = %s

                  AND UserId = 0
                  AND (IsDeleted = 0 OR IsDeleted IS NULL)
                """,
                (db_goal, level)
            )

            row = auth_tbl.cursor.fetchone()
            total_workouts = row["total"] if row else 0

            self.add_program_card(
                program_name=f"{goal_key.replace('_', ' ').title()} {level.title()}",
                difficulty=level,
                total_workouts=total_workouts
            )

    def add_program_card(self, program_name, difficulty, total_workouts):
        banner_map = {
            "beginner": "beginner.jpg",
            "intermediate": "intermediate.jpg",
            "advanced": "advanced.jpg"
        }

        quote_map = {
            "beginner": "Consistency beats perfection every time.",
            "intermediate": "Train with purpose. Grow with discipline.",
            "advanced": "Your mindset is your strongest muscle."
        }

        card = MDCard(
            size_hint_y=None,
            height="200dp",
            radius=[20, 20, 20, 20],
            padding=10,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)
        )

        layout = MDBoxLayout(orientation="vertical", spacing=6)

        image_card = MDCard(
            size_hint_y=None,
            height="140dp",
            radius=[20, 20, 20, 20],
            padding=0,
            elevation=2,
            on_release=lambda x: self.open_admin_program(self.current_goal, difficulty)
        )

        image_card.add_widget(
            FitImage(
                source=banner_map.get(difficulty.lower(), "program_banner.png"),
                keep_ratio=False,
                allow_stretch=True
            )
        )

        layout.add_widget(image_card)

        layout.add_widget(MDLabel(
            text=f"[b]{quote_map.get(difficulty, '')}[/b]",
            markup=True,
            font_size="12sp"
        ))

        layout.add_widget(MDLabel(
            text=f"{difficulty.title()} | {total_workouts} Workouts",
            font_size="12sp"
        ))

        card.add_widget(layout)
        self.ids.admin_wellness_container.add_widget(card)

    def go_to_adminexercise(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_adminarticles(self):
        self.manager.instant_switch("admin_articles")

    def go_to_gainweight(self):
        self.manager.instant_switch("admin_wellnesshub_gainweightsreen")

    def go_to_loseweight(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def go_to_keepfit(self):
        self.manager.instant_switch("admin_wellnesshub_keepfitsreen")

    def go_to_gainmuscles(self):
        self.manager.instant_switch("admin_wellnesshub_gainmusclessreen")

class AdminWorkoutProgramScreen(MDScreen):
    goal = None
    level = None
    program = None
    current_mode = "normal"

    # --------------------------------------------------
    # BASIC SETUP
    # --------------------------------------------------
    def set_program(self, goal, level):
        self.goal = goal
        self.level = level

    def on_pre_enter(self, *args):
        if self.goal and self.level:
            self.load_program()
            if self.current_mode == "condition":
                self.show_condition()
            else:
                self.show_normal()

    def load_program(self):
        self.program = {
            "normal": [],
            "condition": []
        }

        db_goal = normalize_goal(self.goal)

        auth_tbl.cursor.execute(
            """
            SELECT
                Name,
                Sets,
                Reps,
                RestSeconds,
                Meaning,
                Steps,
                Benefits,
                ProgramName,
                Image
            FROM user_exercises
            WHERE UserId = 0
              AND Goal = %s
              AND Difficulty = %s
              AND (IsDeleted = 0 OR IsDeleted IS NULL)
            ORDER BY Created_at ASC
            """,
            (db_goal, self.level)
        )

        rows = auth_tbl.cursor.fetchall()

        for row in rows:
            bucket = normalize_program_name(row["ProgramName"])

            self.program[bucket].append({
                "name": row["Name"],
                "sets": row["Sets"],
                "reps": row["Reps"],
                "rest": row["RestSeconds"],
                "description": row["Meaning"] or "",
                "steps": row["Steps"] or "",
                "benefits": row["Benefits"] or "",
                "image": blob_to_image_path(row["Image"]),
            })

        self.ids.goal_title.text = self.goal.replace("_", " ").title()
        self.ids.level_details.text = (
            f"{self.level.title()} | "
            f"{len(self.program['normal']) + len(self.program['condition'])} Workouts"
        )

    # --------------------------------------------------
    # TOGGLES
    # --------------------------------------------------
    def show_normal(self):
        self.current_mode = "normal"
        self._update_toggle_ui("normal")
        self.load_exercises(self.program["normal"])

    def show_condition(self):
        self.current_mode = "condition"
        self._update_toggle_ui("condition")
        self.load_exercises(self.program["condition"])

    def _update_toggle_ui(self, active):
        ACTIVE_BG = (0.2, 0.6, 0.2, 1)
        INACTIVE_BG = (0.85, 0.9, 0.8, 1)

        ACTIVE_TEXT = (1, 1, 1, 1)
        INACTIVE_TEXT = (0.2, 0.6, 0.2, 1)

        # background
        self.ids.btn_normal.md_bg_color = ACTIVE_BG if active == "normal" else INACTIVE_BG
        self.ids.btn_condition.md_bg_color = ACTIVE_BG if active == "condition" else INACTIVE_BG

        # text color (stable: uses ids)
        self.ids.txt_normal.text_color = ACTIVE_TEXT if active == "normal" else INACTIVE_TEXT
        self.ids.txt_condition.text_color = ACTIVE_TEXT if active == "condition" else INACTIVE_TEXT

    # --------------------------------------------------
    # LOAD EXERCISES
    # --------------------------------------------------
    def load_exercises(self, exercises):
        container = self.ids.exercise_container
        container.clear_widgets()

        if not exercises:
            container.add_widget(
                MDLabel(
                    text="No exercises available.",
                    halign="center",
                    size_hint_y=None,
                    height=dp(50),
                )
            )
            return

        for ex in exercises:
            container.add_widget(self.build_exercise_card(ex))

    def build_exercise_card(self, ex):
        img = ex.get("image", "exercisepic/default.png")

        thumb = FitImage(
            source=img,
            size_hint=(None, None),
            size=(dp(56), dp(56)),
            radius=[12] * 4,
        )

        title = MDLabel(text=ex["name"], bold=True)
        subtitle = MDLabel(
            text=f"{ex['sets']} Sets × {ex['reps']} Reps | Rest {ex['rest']}s",
            theme_text_color="Secondary",
            font_size="12sp",
        )

        text_box = MDBoxLayout(orientation="vertical")
        text_box.add_widget(title)
        text_box.add_widget(subtitle)

        delete_btn = MDIconButton(
            icon="delete",
            theme_icon_color="Custom",
            icon_color=(0.8, 0.1, 0.1, 1),
            on_release=lambda x: self.confirm_delete(ex),
        )

        row = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )

        row.add_widget(thumb)
        row.add_widget(text_box)
        row.add_widget(delete_btn)

        # ✅ THIS IS THE IMPORTANT FIX
        card = MDCard(
            row,  # ← widget passed directly (NO *args)
            size_hint_y=None,
            height=dp(78),
            radius=[18, 18, 18, 18],
            md_bg_color=(0.95, 0.96, 0.92, 1),
            ripple_behavior=True,
            on_release=partial(self.preview_exercise, ex),
        )

        return card

    def update_exercise(self, ex, name, sets, reps, rest, description,
                        steps, benefits, image_bytes,):
        auth_tbl.cursor.execute(
            """
            UPDATE user_exercises
            SET
                Name=%s,
                Sets=%s,
                Reps=%s,
                RestSeconds=%s,
                Meaning=%s,
                Steps=%s,
                Benefits=%s,
                Image=COALESCE(%s, Image)
            WHERE Name=%s
              AND UserId=0
              AND Goal=%s
              AND Difficulty=%s
            """,
            (
                name.strip(),
                int(sets),
                reps.strip(),
                int(rest),
                description.strip(),
                steps.strip(),
                benefits.strip(),
                image_bytes,
                ex["name"],
                normalize_goal(self.goal),
                self.level,
            )
        )
        auth_tbl.db.commit()

        self.edit_ex_dialog.dismiss()
        self.load_program()
        self.show_normal() if self.current_mode == "normal" else self.show_condition()

        if self.current_mode == "condition":
            self.show_condition()
        else:
            self.show_normal()

        self.show_snackbar("Exercise updated successfully!")

    def preview_exercise(self, ex, *args):
        # ---------- IMAGE ----------
        img = ex.get("image", "exerpic_default.png")

        preview_image = FitImage(
            source=img,
            size_hint=(1, None),
            height=dp(180),
            radius=[16] * 4,
        )

        def format_list(title, text):
            if not text.strip():
                return ""
            items = "\n".join(f"• {line}" for line in text.splitlines())
            return f"[b]{title}[/b]\n{items}\n\n"

        preview_text = (
                f"[b]Exercise Name:[/b] {ex['name']}\n\n"
                f"[b]Sets:[/b] {ex['sets']}\n"
                f"[b]Reps:[/b] {ex['reps']}\n"
                f"[b]Rest:[/b] {ex['rest']} seconds\n\n"
                f"[b]Description[/b]\n{ex['description']}\n\n"
                + format_list("Steps", ex["steps"])
                + format_list("Benefits", ex["benefits"])
        )

        preview_label = MDLabel(
            text=preview_text,
            markup=True,
            size_hint_y=None,
            theme_text_color="Custom",
            text_color=(0, 0, 0, 1),
        )
        preview_label.bind(texture_size=preview_label.setter("size"))

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),
            padding=dp(12),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(preview_image)
        content.add_widget(preview_label)

        scroll = MDScrollView(size_hint_y=None, height=dp(420))
        scroll.add_widget(content)

        self.exercise_preview_dialog = MDDialog(
            MDDialogHeadlineText(text="Exercise Preview"),
            MDDialogContentContainer(scroll),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Close"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.exercise_preview_dialog.dismiss(),
                ),
                Widget(size_hint_x=None, width=dp(20)),
                MDButton(
                    MDButtonText(text="Edit"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: (
                        self.exercise_preview_dialog.dismiss(),
                        self.edit_exercise(ex)
                    ),
                ),
            ),
        )
        self.exercise_preview_dialog.open()

    def edit_exercise(self, ex):
        self.exercise_photo_bytes = None

        # ---------- IMAGE (ARTICLE-STYLE) ----------
        self.edit_exercise_image = FitImage(
            source=ex.get("image", "exerpic_default.png"),
            size_hint=(1, None),
            height=dp(160),
            radius=[16, 16, 16, 16],
        )

        image_container = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=(dp(8), dp(8), dp(8), dp(8)),
            size_hint_y=None,
        )
        image_container.bind(minimum_height=image_container.setter("height"))

        image_container.add_widget(self.edit_exercise_image)

        change_image_btn = MDButton(
            MDButtonText(text="Change Image"),
            style="outlined",
            pos_hint={"center_x": 0.5},
            on_release=self.open_image_picker_for_add,
        )
        image_container.add_widget(change_image_btn)

        # ---------- INPUT FIELDS ----------
        name_field = MDTextField(text=ex["name"], mode="outlined")
        sets_field = MDTextField(text=str(ex["sets"]), mode="outlined", input_filter="int")
        reps_field = MDTextField(text=str(ex["reps"]), mode="outlined")
        rest_field = MDTextField(text=str(ex["rest"]), mode="outlined", input_filter="int")
        description_field = MDTextField(text=ex["description"], mode="outlined", multiline=True)
        steps_field = MDTextField(text=ex["steps"], mode="outlined", multiline=True)
        benefits_field = MDTextField(text=ex["benefits"], mode="outlined", multiline=True)

        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(12),
            size_hint_y=None,
        )
        content_box.bind(minimum_height=content_box.setter("height"))

        def add(label, field):
            content_box.add_widget(MDLabel(text=label, role="small"))
            content_box.add_widget(field)

        # ✅ CORRECT CONTAINER
        content_box.add_widget(image_container)

        add("Exercise Name", name_field)
        add("Sets", sets_field)
        add("Reps", reps_field)
        add("Rest Time", rest_field)
        add("Description", description_field)
        add("Steps (one per line)", steps_field)
        add("Benefits (one per line)", benefits_field)

        scroll = MDScrollView(size_hint_y=None, height=dp(420))
        scroll.add_widget(content_box)

        self.edit_ex_dialog = MDDialog(
            MDDialogHeadlineText(text="Edit Exercise"),
            MDDialogContentContainer(scroll),
            MDDialogButtonContainer(
                Widget(),

                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.edit_ex_dialog.dismiss(),
                ),
                Widget(size_hint_x=None, width=dp(20)),

                MDButton(
                    MDButtonText(text="Save Changes"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.update_exercise(
                        ex,
                        name_field.text,
                        sets_field.text,
                        reps_field.text,
                        rest_field.text,
                        description_field.text,
                        steps_field.text,
                        benefits_field.text,
                        self.exercise_photo_bytes,
                    ),
                ),
            ),
        )
        self.edit_ex_dialog.open()

    # DELETE
    # --------------------------------------------------
    def confirm_delete(self, ex):
        dialog = MDDialog(
            MDDialogHeadlineText(text=f"Delete Exercise?"),
            MDDialogSupportingText( text=(
                    "This action cannot be undone. "
                    "The exercise will be removed from the database "
                    "and users will no longer see it."
                )),
            MDDialogButtonContainer(
                Widget(),
                MDButton(MDButtonText(text="Cancel"),
                         style="filled",
                         theme_bg_color="Custom",
                         md_bg_color=(0.6, 0.8, 0.6, 1),
                         on_release=lambda x: dialog.dismiss()),

                Widget(size_hint_x=None, width=dp(20)),   # ✅ pushes buttons to the right

                MDButton(
                    MDButtonText(text="Delete"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.delete_exercise(ex, dialog),
                ),
            ),
            auto_dismiss=False,
        )
        dialog.open()

    def delete_exercise(self, ex, dialog):
        name = ex["name"]

        # 1️⃣ DELETE FROM USER_EXERCISES (ADMIN)
        auth_tbl.cursor.execute(
            """
            DELETE FROM user_exercises
            WHERE Name = %s
              AND Goal = %s
              AND Difficulty = %s
              AND UserId = 0
            """,
            (name, normalize_goal(self.goal), self.level)
        )

        # 2️⃣ DELETE FROM SAVED EXERCISES (ALL USERS)
        auth_tbl.cursor.execute(
            """
            DELETE FROM saved_exercises_by_user
            WHERE Name = %s
            """,
            (name,)
        )

        auth_tbl.db.commit()

        dialog.dismiss()

        # 3️⃣ RELOAD ADMIN UI
        self.load_program()
        if self.current_mode == "condition":
            self.show_condition()
        else:
            self.show_normal()

        self.show_snackbar("Exercise deleted successfully")

    # --------------------------------------------------
    # ADD EXERCISE
    # --------------------------------------------------

    def on_add_image_selected(self, selection):
        if not selection:
            return

        path = selection[0]

        # ✅ store bytes for DB
        with open(path, "rb") as f:
            self.exercise_photo_bytes = f.read()

        # ✅ ADD EXERCISE PREVIEW
        if hasattr(self, "exercise_image"):
            self.exercise_image.source = path
            self.exercise_image.reload()

        # ✅ EDIT EXERCISE PREVIEW (THIS FIXES YOUR ISSUE)
        if hasattr(self, "edit_exercise_image"):
            self.edit_exercise_image.source = path
            self.edit_exercise_image.reload()

    def open_image_picker_for_add(self, *args):
        filechooser.open_file(filters=[("Images", "*.png;*.jpg;*.jpeg;*.webp")],
                              on_selection=self.on_add_image_selected, )

    def open_add_exercise_dialog(self):
        self.new_image_path = ""
        self.exercise_photo_bytes = None

        # ---------- IMAGE PREVIEW ----------
        self.exercise_image = FitImage(
            source="exerpic_default.png",
            size_hint=(1, None),
            height=dp(130),
            radius=[12, 12, 12, 12],
        )

        upload_btn = MDButton(
            MDButtonText(text="Upload Image"),
            style="outlined",
            pos_hint={"center_x": 0.5},
            on_release=self.open_image_picker_for_add,
        )

        image_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint_y=None,
        )
        image_box.bind(minimum_height=image_box.setter("height"))
        image_box.add_widget(self.exercise_image)
        image_box.add_widget(upload_btn)

        # ---------- INPUT FIELDS ----------
        name_field = MDTextField(mode="outlined", size_hint_y=None, height=dp(56))
        sets_field = MDTextField(mode="outlined", input_filter="int", size_hint_y=None, height=dp(56))
        reps_field = MDTextField(mode="outlined", input_filter="int", size_hint_y=None, height=dp(56))
        rest_field = MDTextField(mode="outlined", size_hint_y=None, height=dp(56))
        description_field = MDTextField(mode="outlined", multiline=True, size_hint_y=None, height=dp(120))
        steps_field = MDTextField(mode="outlined", multiline=True, size_hint_y=None, height=dp(120))
        benefits_field = MDTextField(mode="outlined", multiline=True, size_hint_y=None, height=dp(120))

        # ---------- CONTENT ----------
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(12),
            size_hint_y=None,
        )
        content_box.bind(minimum_height=content_box.setter("height"))

        def add_field(label, field):
            content_box.add_widget(
                MDLabel(
                    text=label,
                    role="small",
                    theme_text_color="Custom",
                    text_color=(0.3, 0.3, 0.3, 1),
                    size_hint_y=None,
                    height=dp(20),
                )
            )
            content_box.add_widget(field)

        content_box.add_widget(image_box)
        add_field("Exercise Name", name_field)
        add_field("Sets", sets_field)
        add_field("Reps", reps_field)
        add_field("Rest Time", rest_field)
        add_field("Description", description_field)
        add_field("Steps (one per line)", steps_field)
        add_field("Benefits (one per line)", benefits_field)

        scroll = MDScrollView(size_hint_y=None, height=dp(420))
        scroll.add_widget(content_box)

        # ---------- DIALOG ----------
        self._add_dialog = MDDialog(
            MDDialogHeadlineText(text="Add New Exercise"),
            MDDialogContentContainer(scroll),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self._add_dialog.dismiss(),
                ),

                Widget(size_hint_x=None, width=dp(20)),

                MDButton(
                    MDButtonText(text="Add Exercise"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.save_new_exercise(
                        name_field.text,
                        sets_field.text,
                        reps_field.text,
                        rest_field.text,
                        description_field.text,
                        steps_field.text,
                        benefits_field.text,
                        self.exercise_photo_bytes,
                    ),
                ),
            ),
        )

        self._add_dialog.open()

    def save_new_exercise(
            self,
            name,
            sets,
            reps,
            rest,
            description,
            steps,
            benefits,
            image_bytes,
    ):
        # ---------- TRIM INPUTS ----------
        name = name.strip()
        description = description.strip()
        steps = "\n".join(s.strip() for s in steps.splitlines() if s.strip())
        benefits = "\n".join(b.strip() for b in benefits.splitlines() if b.strip())

        # ---------- VALIDATION ----------
        if not name:
            self.show_snackbar("Exercise name is required.", success=False)
            return

        if not sets:
            self.show_snackbar("Sets is required.", success=False)
            return

        if not reps:
            self.show_snackbar("Reps is required.", success=False)
            return

        if not rest:
            self.show_snackbar("Rest time is required.", success=False)
            return

        if not description:
            self.show_snackbar("Description is required.", success=False)
            return

        if not steps:
            self.show_snackbar("Steps are required.", success=False)
            return

        if not benefits:
            self.show_snackbar("Benefits are required.", success=False)
            return

        if not image_bytes:
            self.show_snackbar("Exercise image is required.", success=False)
            return

        # ---------- SAFE CONVERSIONS ----------
        try:
            sets = int(sets)
            rest = int(rest)
        except ValueError:
            self.show_snackbar("Sets and rest time must be numbers.", success=False)
            return

        reps = str(reps)

        # ---------- SAVE ----------
        auth_tbl.cursor.execute(
            """
            INSERT INTO user_exercises
            (
                UserId, Goal, Category, Name,
                Meaning, Steps, Benefits, Image,
                Difficulty, ProgramName,
                Sets, Reps, RestSeconds,
                Created_at
            )
            VALUES
            (
                0, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                NOW()
            )
            """,
            (
                normalize_goal(self.goal),
                self.level,
                name,
                description,
                steps,
                benefits,
                image_bytes,
                self.level,
                self.current_mode,
                sets,
                reps,
                rest,
            )
        )
        auth_tbl.db.commit()

        self._add_dialog.dismiss()
        self.load_program()

        if self.current_mode == "condition":
            self.show_condition()
        else:
            self.show_normal()

        self.show_snackbar("Exercise added successfully!", success=True)

    def show_snackbar(self, text, success=True, bg_color=None):
        if bg_color is None:
            bg_color = (0.2, 0.7, 0.2, 1) if success else (0.8, 0.1, 0.1, 1)

        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp"
            ),
            duration=2,
            size_hint=(0.9, None),
            height="50dp",
            pos_hint={"center_x": 0.5, "y": 0.02},
            md_bg_color=bg_color,
            radius=[20, 20, 20, 20],
        )
        snack.open()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "images")

class admin_articlesScreen(MDScreen):
    article_count = NumericProperty(0)


    def on_pre_enter(self):
        self.load_articles()
        self.edit_article_photo_path = None
        self.edit_article_image = None

    def load_articles(self):
        container = self.ids.admin_wellness_container
        container.clear_widgets()

        rows = auth_tbl.get_all_articles()
        self.article_count = len(rows)

        if not rows:
            container.add_widget(
                MDLabel(
                    text="No articles yet. Click 'Add New' to create one.",
                    halign="center",
                    size_hint_y=None,
                    height=dp(50),
                )
            )
            return

        for row in rows:
            article = dict(row)  # ✅ COPY, DO NOT MUTATE DB ROW

            img = article.get("image")

            if not img or not isinstance(img, str):
                article["image"] = "artipic_default.png"
            else:
                # ✅ Convert DB path to absolute path ONLY for checking
                abs_img = os.path.join(BASE_DIR, img)

                if not os.path.exists(abs_img):
                    article["image"] = "artipic_default.png"
                else:
                    # ✅ KEEP DATABASE IMAGE
                    article["image"] = img

            card = Factory.AdminArticleCard(article=article)
            container.add_widget(card)

    def open_add_article_dialog(self):
        self.selected_image_path = ""
        self.article_photo_path = None
        self.article_photo_bytes = None

        # ---------- IMAGE PREVIEW ----------
        self.article_image = FitImage(
            source="artipic_default.png",
            size_hint=(1, None),
            height=dp(130),
            radius=[12, 12, 12, 12],
        )

        upload_btn = MDButton(
            MDButtonText(text="Upload Image"),
            style="outlined",
            pos_hint={"center_x": 0.5},
            on_release=self.open_article_file_manager,
        )

        image_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint_y=None,
        )
        image_box.bind(minimum_height=image_box.setter("height"))
        image_box.add_widget(self.article_image)
        image_box.add_widget(upload_btn)

        # ---------- INPUT FIELDS ----------
        category_field = MDTextField(mode="outlined", size_hint_y=None, height=dp(56))
        title_field = MDTextField(mode="outlined", size_hint_y=None, height=dp(56))
        author_field = MDTextField(mode="outlined", size_hint_y=None, height=dp(56))
        date_field = MDTextField(mode="outlined", size_hint_y=None, height=dp(56))
        body_field = MDTextField(mode="outlined", multiline=True, size_hint_y=None, height=dp(180))

        # ---------- CONTENT ----------
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(12),
            size_hint_y=None,
        )
        content_box.bind(minimum_height=content_box.setter("height"))

        def add_field(label, field):
            content_box.add_widget(
                MDLabel(
                    text=label,
                    role="small",
                    theme_text_color="Custom",
                    text_color=(0.3, 0.3, 0.3, 1),
                    size_hint_y=None,
                    height=dp(20),
                )
            )
            content_box.add_widget(field)

        content_box.add_widget(image_box)
        add_field("Category", category_field)
        add_field("Article Title", title_field)
        add_field("Author’s Name", author_field)
        add_field("Date / Year", date_field)
        add_field("Article Body (Full Content)", body_field)

        scroll = MDScrollView(size_hint_y=None, height=dp(420))
        scroll.add_widget(content_box)

        self.add_dialog = MDDialog(
            MDDialogHeadlineText(text="Add New Article"),
            MDDialogContentContainer(scroll),
            MDDialogButtonContainer(
                Widget(),
                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.add_dialog.dismiss(),
                ),

                Widget(size_hint_x=None, width=dp(20)),  # ✅ space between buttons

                MDButton(
                    MDButtonText(text="Add Article"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.add_article(
                        category_field.text,
                        title_field.text,
                        author_field.text,
                        date_field.text,
                        body_field.text,
                        self.article_photo_bytes,
                    ),
                ),
            ),
        )

        self.add_dialog.open()

    def open_article_file_manager(self, *args):
        filechooser.open_file(on_selection=self.on_article_file_select)

    def on_article_file_select(self, selection):
        if not selection:
            return

        src_path = selection[0]
        ext = os.path.splitext(src_path)[1].lower()

        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            self.show_msg("Invalid image type.", bg_color=(0.8, 0.1, 0.1, 1))
            return

        try:
            os.makedirs(IMAGE_DIR, exist_ok=True)

            filename = f"article_{int(time.time())}{ext}"
            abs_save_path = os.path.join(IMAGE_DIR, filename)

            with open(src_path, "rb") as src, open(abs_save_path, "wb") as dst:
                dst.write(src.read())

            # ✅ STORE RELATIVE PATH IN DB
            self.article_photo_path = f"images/{filename}"

            # ✅ PREVIEW IMAGE
            self.article_image.source = self.article_photo_path
            self.article_image.reload()

            self.show_msg("Article image uploaded!")

        except Exception as e:
            print("Image error:", e)
            self.show_msg("Failed to upload image.", bg_color=(0.8, 0.1, 0.1, 1))

    def open_article_file_manager_for_edit(self, *args):
        filechooser.open_file(on_selection=self.on_edit_article_file_select)

    def on_edit_article_file_select(self, selection):
        if not selection:
            return

        src_path = selection[0]
        ext = os.path.splitext(src_path)[1].lower()

        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            self.show_msg("Invalid image type.", bg_color=(0.8, 0.1, 0.1, 1))
            return

        try:
            os.makedirs(IMAGE_DIR, exist_ok=True)

            filename = f"article_{int(time.time())}{ext}"
            abs_save_path = os.path.join(IMAGE_DIR, filename)

            with open(src_path, "rb") as src, open(abs_save_path, "wb") as dst:
                dst.write(src.read())

            # ✅ SAVE NEW IMAGE PATH (RELATIVE)
            self.edit_article_photo_path = f"images/{filename}"

            # ✅ UPDATE PREVIEW
            self.edit_article_image.source = self.edit_article_photo_path
            self.edit_article_image.reload()

            self.show_msg("Article image updated!")

        except Exception as e:
            print("Edit image error:", e)
            self.show_msg("Failed to update image.", bg_color=(0.8, 0.1, 0.1, 1))

    def edit_article(self, article):
        """Open dialog to edit existing article"""

        self.edit_article_photo_path = None  # reset

        # ---------- IMAGE PREVIEW ----------
        current_image = article.get("image", "artipic_default.png")

        self.edit_article_image = FitImage(
            source=current_image,
            size_hint=(1, None),
            height=dp(130),
            radius=[12, 12, 12, 12],
        )

        upload_btn = MDButton(
            MDButtonText(text="Change Image"),
            style="outlined",
            pos_hint={"center_x": 0.5},
            on_release=self.open_article_file_manager_for_edit,
        )

        image_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint_y=None,
        )
        image_box.bind(minimum_height=image_box.setter("height"))
        image_box.add_widget(self.edit_article_image)
        image_box.add_widget(upload_btn)

        # ---------- INPUT FIELDS ----------
        category_field = MDTextField(
            mode="outlined",
            text=article.get("category", ""),
            size_hint_y=None,
            height=dp(56)
        )

        title_field = MDTextField(
            mode="outlined",
            text=article.get("title", ""),
            size_hint_y=None,
            height=dp(56)
        )

        author_field = MDTextField(
            mode="outlined",
            text=article.get("author", ""),
            size_hint_y=None,
            height=dp(56)
        )

        date_field = MDTextField(
            mode="outlined",
            text=article.get("date", ""),
            size_hint_y=None,
            height=dp(56)
        )

        body_field = MDTextField(
            mode="outlined",
            multiline=True,
            text=article.get("body", ""),
            size_hint_y=None,
            height=dp(180),
        )

        # ---------- CONTENT ----------
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(12),
            size_hint_y=None,
        )
        content_box.bind(minimum_height=content_box.setter("height"))

        def add_field(label, field):
            content_box.add_widget(
                MDLabel(
                    text=label,
                    role="small",
                    theme_text_color="Custom",
                    text_color=(0.3, 0.3, 0.3, 1),
                    size_hint_y=None,
                    height=dp(20),
                )
            )
            content_box.add_widget(field)

        content_box.add_widget(image_box)
        add_field("Category", category_field)
        add_field("Article Title", title_field)
        add_field("Author Name", author_field)
        add_field("Date / Year", date_field)
        add_field("Article Body / Content", body_field)

        scroll = MDScrollView(size_hint_y=None, height=dp(420))
        scroll.add_widget(content_box)

        self.edit_dialog = MDDialog(
            MDDialogHeadlineText(text="Edit Article"),
            MDDialogContentContainer(scroll),
            MDDialogButtonContainer(
                Widget(),

                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.edit_dialog.dismiss(),
                ),

                Widget(size_hint_x=None, width=dp(20)),

                MDButton(
                    MDButtonText(text="Save Changes"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.update_article(
                        article.get("ArticleId"),
                        category_field.text,
                        title_field.text,
                        author_field.text,
                        date_field.text,
                        body_field.text,
                        article.get("image"),
                    ),
                ),
            ),
        )
        self.edit_dialog.open()

    def add_article(self, category, title, author, date, body, _image):
        if not all([category, title, author, date, body]):
            self.show_msg("Please fill all required fields", bg_color=(0.9, 0.6, 0.1, 1))
            return

        if not self.article_photo_path:
            self.show_msg("Please upload an article image", bg_color=(0.9, 0.2, 0.2, 1))
            return

        article_data = {
            "category": category.strip(),
            "title": title.strip(),
            "author": author.strip(),
            "date": date.strip(),
            "body": body.strip(),
            "image": self.article_photo_path,  # ✅ STORED PATH
        }

        success = auth_tbl.add_article_to_db(article_data)

        if success:
            self.add_dialog.dismiss()
            self.load_articles()
            self.show_msg("Article added successfully!")
        else:
            self.show_msg("Failed to add article", bg_color=(0.8, 0.1, 0.1, 1))

    def confirm_delete(self, article_id):
        """Show confirmation dialog before deleting"""
        from kivymd.uix.dialog import MDDialog, MDDialogHeadlineText, MDDialogSupportingText, MDDialogButtonContainer
        from kivymd.uix.button import MDButton, MDButtonText

        from kivy.uix.widget import Widget
        from kivy.metrics import dp

        self.delete_dialog = MDDialog(
            MDDialogHeadlineText(text="Delete Article?"),
            MDDialogSupportingText(
                text=(
                    "This action cannot be undone. "
                    "The article will be removed from the database "
                    "and users will no longer see it."
                )
            ),
            MDDialogButtonContainer(
                Widget(),  # ✅ pushes buttons to the right

                MDButton(
                    MDButtonText(text="Cancel"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.delete_dialog.dismiss(),
                ),

                Widget(size_hint_x=None, width=dp(20)),  # ✅ SPACE BETWEEN BUTTONS

                MDButton(
                    MDButtonText(text="Delete"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: self.delete_article(article_id),
                ),
            ),
            auto_dismiss=False,
        )
        self.delete_dialog.open()

    def delete_article(self, article_id):
        """Delete article from database"""

        success = auth_tbl.delete_article(article_id)

        if success:
            auth_tbl.delete_saved_articles_by_article_id(article_id)
            self.load_articles()
            self.delete_dialog.dismiss()
            self.show_msg("Article deleted successfully!")
        else:
            self.show_msg(
                "Failed to delete article.",
                bg_color=(0.8, 0.1, 0.1, 1)
            )

    def update_article(self, article_id, category, title, author, date, body, image):
        """Update article in database"""
        if not all([category, title, author, date, body]):
            self.show_msg(
                "Please fill all required fields",
                bg_color=(0.9, 0.6, 0.1, 1)
            )
            return

        article_data = {
            "category": category.strip(),
            "title": title.strip(),
            "author": author.strip(),
            "date": date.strip(),
            "body": body.strip(),
            "image": self.edit_article_photo_path or image.strip() or "artipic_default.png"
        }

        success = auth_tbl.update_article(article_id, article_data)

        if success:
            auth_tbl.update_saved_articles_by_article_id(article_id, article_data)
            self.edit_dialog.dismiss()
            self.load_articles()
            self.show_msg("Article updated successfully!")
        else:
            self.show_msg(
                "Failed to update article.",
                bg_color=(0.8, 0.1, 0.1, 1)
            )

    def go_to_adminexercise(self):
        self.manager.instant_switch("admin_wellnesshubsreen")

    def preview_article(self, article):
        """Preview article before editing"""

        # ---------- IMAGE ----------
        img = article.get("image", "artipic_default.png")
        abs_img = os.path.join(BASE_DIR, img)

        if not os.path.exists(abs_img):
            img = "artipic_default.png"

        preview_image = FitImage(
            source=img,
            size_hint=(1, None),
            height=dp(160),
            radius=[16, 16, 16, 16],
        )

        # ---------- TEXT ----------
        preview_label = MDLabel(
            text=(
                f"[b]Category:[/b] {article.get('category', '')}\n\n"
                f"[b]Title:[/b] {article.get('title', '')}\n\n"
                f"[b]Author:[/b] {article.get('author', '')}\n\n"
                f"[b]Date:[/b] {article.get('date', '')}\n\n"
                f"[b]Body:[/b]\n{article.get('body', '')}"
            ),
            markup=True,
            size_hint_y=None,
            theme_text_color="Custom",
            text_color=(0, 0, 0, 1),
        )
        preview_label.bind(texture_size=preview_label.setter("size"))

        # ---------- CONTENT ----------
        content_box = MDBoxLayout(
            orientation="vertical",
            spacing=dp(14),
            padding=dp(12),
            size_hint_y=None,
        )
        content_box.bind(minimum_height=content_box.setter("height"))

        content_box.add_widget(preview_image)
        content_box.add_widget(preview_label)

        scroll = MDScrollView(size_hint_y=None, height=dp(420))
        scroll.add_widget(content_box)

        # ---------- DIALOG ----------
        self.preview_dialog = MDDialog(
            MDDialogHeadlineText(text="Article Preview"),
            MDDialogContentContainer(scroll),
            MDDialogButtonContainer(
                Widget(),

                MDButton(
                    MDButtonText(text="Close"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.6, 0.8, 0.6, 1),
                    on_release=lambda x: self.preview_dialog.dismiss(),
                ),

                Widget(size_hint_x=None, width=dp(20)),

                MDButton(
                    MDButtonText(text="Edit"),
                    style="filled",
                    theme_bg_color="Custom",
                    md_bg_color=(0.1, 0.7, 0.1, 1),
                    on_release=lambda x: (
                        self.preview_dialog.dismiss(),
                        self.edit_article(article)
                    ),
                ),
            ),
        )
        self.preview_dialog.open()

    def show_msg(self, text, success=True, bg_color=None):
        if bg_color is None:
            bg_color = (0.2, 0.7, 0.2, 1) if success else (0.8, 0.1, 0.1, 1)

        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp"
            ),
            duration=2,
            size_hint=(0.9, None),
            height="50dp",
            pos_hint={"center_x": 0.5, "y": 0.02},
            md_bg_color=bg_color,
            radius=[20, 20, 20, 20],
        )
        snack.open()

    def go_to_adminarticles(self):
        self.manager.instant_switch("admin_articles")


class AdminArticleCard(MDCard):
    article = DictProperty({})

def migrate_exercises_json_to_db():
    import json

    SYSTEM_USER_ID = 0

    # -----------------------------
    # LOAD WORKOUTS
    # -----------------------------
    with open("Workouts.json", "r", encoding="utf-8") as f:
        workouts = json.load(f)

    # -----------------------------
    # LOAD & NORMALIZE EXERCISE DETAILS
    # -----------------------------
    with open("ExerciseDetails.json", "r", encoding="utf-8") as f:
        raw_details = json.load(f)["exercises"]

    details = {
        normalize_exercise_name(name): data
        for name, data in raw_details.items()
    }

    # -----------------------------
    # BUILD IMAGE INDEX
    # -----------------------------
    image_index = build_exercise_image_index()

    # -----------------------------
    # PRELOAD EXISTING ROWS
    # -----------------------------
    auth_tbl.cursor.execute("""
        SELECT Name, Goal, Difficulty, ProgramName
        FROM user_exercises
        WHERE UserId = %s
    """, (SYSTEM_USER_ID,))

    existing = {
        (row["Name"], row["Goal"], row["Difficulty"], row["ProgramName"])
        for row in auth_tbl.cursor.fetchall()
    }

    # -----------------------------
    # INSERT SQL
    # -----------------------------
    insert_sql = """
        INSERT INTO user_exercises
        (UserId, Goal, Name, Meaning, Steps, Benefits, Image,
         Difficulty, ProgramName,
         Sets, Reps, RestSeconds,
         Created_at, Updated_at)
        VALUES
        (%s, %s, %s, %s, %s, %s, %s,
         %s, %s,
         %s, %s, %s,
         NOW(), NOW())
    """

    added = skipped = 0

    GOAL_MAP = {
        "loss weight": "lose_weight",
        "lose weight": "lose_weight",
        "gain weight": "gain_weight",
        "gain muscle": "gain_muscle",
        "gain muscles": "gain_muscle",
        "maintain weight": "keep_fit",
        "keep fit": "keep_fit",
    }

    # -----------------------------
    # MIGRATION LOOP
    # -----------------------------
    for goal_name, levels in workouts["goals"].items():
        raw_goal = goal_name.strip().lower().replace("_", " ")

        if raw_goal not in GOAL_MAP:
            print(f"❌ Invalid goal in JSON: {goal_name}")
            continue

        goal = GOAL_MAP[raw_goal]

        for difficulty, level_data in levels.items():
            for program_type in ("normal", "health_condition"):

                program_name = (
                    "Health Condition"
                    if program_type == "health_condition"
                    else "Normal"
                )

                for ex in level_data.get(program_type, []):

                    raw_name = (ex.get("name") or "").strip()
                    if not raw_name:
                        continue

                    row_key = (raw_name, goal, difficulty, program_name)
                    if row_key in existing:
                        skipped += 1
                        continue

                    normalized = normalize_exercise_name(raw_name)

                    # -----------------------------
                    # SAFE DETAIL LOOKUP
                    # -----------------------------
                    meaning, steps, benefits = get_exercise_detail(details, normalized)

                    # ==============================
                    # INSERT NEW ROW
                    # ==============================
                    image_path = get_exercise_image(image_index, normalized)
                    image_blob = load_image_blob(image_path)

                    auth_tbl.cursor.execute(
                        insert_sql,
                        (
                            SYSTEM_USER_ID,
                            goal,
                            raw_name,
                            meaning,
                            steps,
                            benefits,

                            image_blob,
                            difficulty,
                            program_name,
                            safe_int(ex.get("sets"), 3),
                            str(ex.get("reps", "")),
                            safe_int(ex.get("rest"), 60),
                        ),
                    )

                    auth_tbl.db.commit()
                    existing.add(row_key)
                    added += 1

                print("\n🎉 Migration Completed")
                print(f"✅ Rows added: {added}")
                print(f"⚠️ Rows skipped (duplicates only): {skipped}")


def safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default

def migrate_json_to_db():
    """One-time migration: Import articles from JSON to database safely"""
    import json
    import os

    json_path = os.path.join("assets", "articles.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("❌ Failed to load JSON:", e)
        return

    # Get all existing article titles to prevent duplicates
    existing_articles = auth_tbl.get_all_articles()
    existing_titles = [a["title"] for a in existing_articles]

    # Counter for tracking
    added_count = 0
    skipped_count = 0

    # Loop through all categories in the JSON
    for category_name, articles in data.items():

        # Handle "featured" (single dict) vs "popular" (list of dicts)
        if isinstance(articles, dict):
            # Single article (e.g., "featured")
            articles_list = [articles]
        elif isinstance(articles, list):
            # Multiple articles (e.g., "popular")
            articles_list = articles
        else:
            print(
                f"⚠️ Unexpected data type for '{category_name}': {type(articles)}")
            continue

        # Now loop through the normalized list
        for article in articles_list:
            try:
                title = article.get("title", "")

                # Skip if article already exists
                if title in existing_titles:
                    print(f"⚠️ Article '{title}' already exists. Skipping.")
                    skipped_count += 1
                    continue

                # Add article to database
                success = auth_tbl.add_article_to_db(article)

                if success:
                    print(f"✅ Added article: '{title}'")
                    # Prevent duplicates in same run
                    existing_titles.append(title)
                    added_count += 1
                else:
                    print(f"❌ Failed to add article '{title}'")

            except Exception as e:
                print(f"❌ Error processing article: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n🎉 Migration complete!")
    print(f"   ✅ Added: {added_count} articles")
    print(f"   ⚠️ Skipped: {skipped_count} articles (already exist)")



class WindowManager(MDScreenManager):

    def __init__(self, **kwargs):
        # ★ Global fade transition for ALL screens
        super().__init__(transition=FadeTransition(duration=0.25), **kwargs)
        self.user_data = {}

        # ★ Instant transition (no fade) for tabs only

    def instant_switch(self, next_screen_name):
        self.transition.duration = 0
        self.current = next_screen_name
        self.transition.duration = 0.25  # restore fade for other screens


class FitnessApp(MDApp):
    current_user_id = None
    edit_post_dialog = None
    current_user_name = None  # stay
    store = None  # stay

#stay
    def reset_all(self):
        if self.store and self.store.exists("user"):
            self.store.delete("user")

        self.current_user_id = None
        self.current_user_name = None

        sm = self.root

        for screen in sm.screens:
            if hasattr(screen, "user_id"):
                screen.user_id = None
            if hasattr(screen, "reset"):
                screen.reset()

        # ALWAYS go to welcome on logout
        sm.transition.direction = "right"
        sm.current = "welcome_screen"

        welcome = sm.get_screen("welcome_screen")
        welcome.opacity = 1
        welcome.ids.indicator.stop()
        welcome.ids.indicator.start()

        Clock.schedule_once(self.stop_loading_indicator, 1)

    def go_to_create_post(self):
        create_screen = self.root.get_screen("create_post_screen")
        create_screen.set_user_id(self.current_user_id)
        create_screen.origin = "createpost"
        self.root.current = "create_post_screen"

    # refresh wall
    def refresh_wall(self):
        print("Refreshing Fitness Wall...")

        home_screen = self.root.get_screen("dashboard_screen")
        feed_box = home_screen.ids.feed_box

        # clear old posts
        feed_box.clear_widgets()

        # fetch new posts
        posts = auth_tbl.get_all_posts()

        for post in posts:
            card = self.create_post_card(post)
            # Prevent crash if card failed to build
            if card is not None:
                feed_box.add_widget(card)
            else:
                print("Skipping invalid card")

    def edit_post(self, card):
        self.open_edit_post_dialog(card)

    def open_edit_post_dialog(self, card):

        if hasattr(self, "post_menu") and self.post_menu:
            self.post_menu.dismiss()

        if self.edit_post_dialog:
            self.edit_post_dialog.dismiss()
            self.edit_post_dialog = None

        # store reference to edited card
        self.editing_card = card
        self.edit_image_path = None

        content = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(16),
            padding=(dp(24), dp(16), dp(24), dp(16)),
        )

        # ✍️ TEXT FIELD
        self.edit_textfield = MDTextField(
            text=card.ids.p_text.text,
            multiline=True,
            mode="outlined",
            max_height=dp(150),
            line_color_focus=(0.1, 0.7, 0.1, 1),
            cursor_color=(0.1, 0.7, 0.1, 1),
        )
        content.add_widget(self.edit_textfield)
        # ➕ ADD PHOTO BUTTON (TEXT-ONLY POSTS ONLY)
        if not card.ids.p_image.texture:
            self.edit_add_photo_btn = MDButton(
                style="text",
                pos_hint={"center_x": 0.5},
            )
            self.edit_add_photo_btn.add_widget(MDButtonText(text="Add Photo"))
            self.edit_add_photo_btn.on_release = lambda *a: self.pick_edit_image()
            content.add_widget(self.edit_add_photo_btn)
        else:
            self.edit_add_photo_btn = None

        # 🖼 IMAGE PREVIEW
        # 🖼 IMAGE + BUTTON CONTAINER
        image_section = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
        )

        # Image preview
        self.edit_preview = Image(
            size_hint_y=None,
            height=dp(180) if card.ids.p_image.height > 0 else 0,
            allow_stretch=True,
            keep_ratio=True,
        )

        if card.ids.p_image.texture:
            self.edit_preview.texture = card.ids.p_image.texture

        image_section.add_widget(self.edit_preview)

        # Buttons row
        img_buttons = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
            adaptive_width=True,
            pos_hint={"center_x": 0.5},
        )

        change_btn = MDButton(
            style="text",
            on_release=lambda *a: self.pick_edit_image(),
        )
        change_btn.add_widget(MDButtonText(text="Change Photo"))

        remove_btn = MDButton(
            style="text",
            on_release=lambda *a: self.remove_edit_image(),
        )
        remove_btn.add_widget(MDButtonText(text="Remove Photo"))

        # 🔥 TOGGLE VISIBILITY BASED ON IMAGE
        if not card.ids.p_image.texture:
            # TEXT-ONLY POST
            change_btn.opacity = 0
            change_btn.disabled = True

            remove_btn.opacity = 0
            remove_btn.disabled = True

        img_buttons.add_widget(change_btn)
        img_buttons.add_widget(remove_btn)

        image_section.add_widget(img_buttons)

        # 🔑 IMPORTANT: manually control height
        if card.ids.p_image.texture:
            image_section.height = self.edit_preview.height + dp(48)
        else:
            image_section.height = 0

        # ✅ THIS WAS MISSING
        content.add_widget(image_section)

        # ⬇️ SPACER para itulak pababa ang Cancel / Save
        content.add_widget(
            MDBoxLayout(
                size_hint_y=None,
                height=dp(20),
            )
        )

        # 🔘 ACTION BUTTONS
        buttons = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(24),
            adaptive_width=True,
            pos_hint={"center_x": 0.5},
        )

        cancel_btn = MDButton(
            style="filled",
            theme_bg_color="Custom",
            md_bg_color=(0.6, 0.8, 0.6, 1),
            radius=[20, 20, 20, 20],
            on_release=lambda *a: self.edit_post_dialog.dismiss(),
        )
        cancel_btn.add_widget(MDButtonText(text="Cancel"))

        save_btn = MDButton(
            style="filled",
            theme_bg_color="Custom",
            md_bg_color=(0.1, 0.7, 0.1, 1),
            radius=[20, 20, 20, 20],
            on_release=lambda *a: self.save_edited_post(card),
        )
        save_btn.add_widget(MDButtonText(text="Save"))

        buttons.add_widget(cancel_btn)
        buttons.add_widget(save_btn)
        content.add_widget(buttons)

        self.edit_post_dialog = MDDialog(
            MDDialogHeadlineText(text="Edit Post"),
            MDDialogContentContainer(content),
            auto_dismiss=False,
        )

        self.edit_post_dialog.open()

    def on_edit_image_selected(self, selection):
        if not selection:
            return

        path = selection[0].lower()
        allowed = (".png", ".jpg", ".jpeg", ".webp")

        if not path.endswith(allowed):
            self.show_edit_snackbar("Only PNG, JPG, or WEBP images are allowed.")
            return

        # store new image path
        self.edit_image_path = path

        # update preview
        self.edit_preview.source = path
        self.edit_preview.height = dp(180)

        # 🔥 EXPAND IMAGE SECTION (same UI as existing photo posts)
        image_section = self.edit_preview.parent
        image_section.height = self.edit_preview.height + dp(48)

        # 🔥 SHOW Change / Remove buttons
        for widget in image_section.children:
            if isinstance(widget, MDBoxLayout):  # button row
                for btn in widget.children:
                    btn.opacity = 1
                    btn.disabled = False

        # 🔥 HIDE Add Photo button after image is added
        if hasattr(self, "edit_add_photo_btn") and self.edit_add_photo_btn:
            self.edit_add_photo_btn.opacity = 0
            self.edit_add_photo_btn.disabled = True

    def save_edited_post(self, card):
        new_text = self.edit_textfield.text.strip()
        post_id = card.post_id


        # 🚫 PROFANITY CHECK (SAME AS CREATE POST)
        if has_profanity(new_text):
            self.show_msg(
                "Your post violates community guidelines.\n"
                "Please revise your content before saving."
            )
            return

        # UPDATE TEXT
        auth_tbl.update_post_content(post_id, new_text)
        card.ids.p_text.text = new_text


        # UPDATE IMAGE
        if self.edit_image_path == "__REMOVE__":
            auth_tbl.remove_post_image(post_id)
            card.ids.p_image.texture = None
            card.ids.p_image.source = ""
            card.ids.p_image.height = 0

        elif self.edit_image_path:
            try:
                # READ IMAGE AS BYTES
                with open(self.edit_image_path, "rb") as f:
                    img_bytes = f.read()

                # SAVE BYTES TO DB
                auth_tbl.update_post_image(post_id, img_bytes)

                # DETECT IMAGE TYPE
                img_type = self.detect_image_ext(img_bytes)

                if not img_type:
                    raise ValueError("Unsupported image format")

                from kivy.clock import Clock

                img = CoreImage(io.BytesIO(img_bytes), ext=img_type or "jpg").texture

                from kivy.clock import Clock

                img = CoreImage(io.BytesIO(img_bytes), ext=img_type or "jpg").texture

                def apply_texture(dt):
                    img_widget = card.ids.p_image
                    img_widget.texture = img
                    img_widget.texture_size = img.size  # ⭐ THIS IS THE KEY

                Clock.schedule_once(apply_texture, 0)

            except Exception as e:
                print("IMAGE UPDATE ERROR:", e)
                card.ids.p_image.texture = None
                card.ids.p_image.height = 0

        # CLOSE DIALOG
        self.edit_post_dialog.dismiss()
        self.edit_post_dialog = None

        self.show_edit_snackbar("Post updated successfully")

    def show_msg(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 0.3, 0.3, 1),
                font_size="15sp",
                size_hint_y=None,
                height=dp(48),
                text_size=(None, None),
            ),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            size_hint_x=0.9,
            adaptive_height=True,  # ⭐ IMPORTANT
            padding=(dp(16), dp(16)),
            elevation=6,
        )
        snack.open()

    def open_delete_post_dialog(self, card):
        if hasattr(self, "post_menu") and self.post_menu:
            self.post_menu.dismiss()

        if hasattr(self, "delete_post_dialog") and self.delete_post_dialog:
            self.delete_post_dialog.dismiss()
            self.delete_post_dialog = None

        self.delete_post_dialog = MDDialog(
            MDDialogHeadlineText(text="Delete post?"),

            MDDialogContentContainer(
                MDBoxLayout(
                    MDLabel(
                        text="This post will be permanently deleted.",
                        halign="center",
                    ),

                    MDBoxLayout(size_hint_y=None, height=dp(25)),

                    MDBoxLayout(
                        MDButton(
                            MDButtonText(text="Cancel"),
                            style="filled",
                            theme_bg_color="Custom",
                            md_bg_color=(0.6, 0.8, 0.6, 1),
                            radius=[20, 20, 20, 20],
                            on_release=lambda *a: self.delete_post_dialog.dismiss(),
                        ),
                        MDButton(
                            MDButtonText(text="Delete"),
                            style="filled",
                            theme_bg_color="Custom",
                            md_bg_color=(0.1, 0.7, 0.1, 1),
                            radius=[20, 20, 20, 20],
                            on_release=lambda *a: self.confirm_delete_post(card),
                        ),

                        orientation="horizontal",
                        spacing=dp(24),
                        adaptive_width=True,
                        pos_hint={"center_x": 0.5},
                    ),

                    orientation="vertical",
                    adaptive_height=True,
                    padding=(dp(24), dp(2), dp(24), dp(16)),
                    spacing=dp(20),
                )
            ),

            auto_dismiss=False,
        )

        self.delete_post_dialog.open()

    def confirm_delete_post(self, card, *args):
        # close dialog
        self.delete_post_dialog.dismiss()
        self.delete_post_dialog = None

        if auth_tbl.delete_post(card.post_id):
            if card.parent:
                card.parent.remove_widget(card)

            # ✅ SUCCESS CONFIRMATION
            self.show_edit_snackbar("Post deleted successfully")


            print("POST DELETED:", card.post_id)

        else:
            # ❌ FAILED CONFIRMATION
            self.show_edit_snackbar("Failed to delete post")


            print("FAILED TO DELETE POST")

    def open_post_menu(self, card):

        # Container ng mga buttons
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=(0, dp(16), 0, dp(16)),
            adaptive_height=True,
        )

        # Helper to create menu rows
        def add_item(label, callback):
            btn = MDButton(
                style="text",
                on_release=lambda *a: (
                    self.post_menu.dismiss(),
                    callback(card)
                ),
            )
            btn.add_widget(MDButtonText(text=label))
            content.add_widget(btn)

        add_item("Edit Post", self.edit_post)
        add_item("Edit Privacy", self.open_privacy_menu)
        add_item("Delete Post", self.open_delete_post_dialog)

        # The centered dialog
        self.post_menu = MDDialog(
            MDDialogHeadlineText(text="Post Options"),
            MDDialogContentContainer(content),
            auto_dismiss=True
        )

        self.post_menu.open()

    def _fix_menu_position(self, card):
        try:
            # ❗ Actual dropdown root overlay (THIS appears on screen)
            overlay = self.menu.ids.get("md_menu_overlay")

            if not overlay:
                # Retry until overlay exists
                Clock.schedule_once(lambda dt: self._fix_menu_position(card), 0.05)
                return

            btn = card.ids.p_menu_button

            # TRUE global coords of button
            bx, by = btn.to_window(btn.center_x, btn.center_y)

            # Get final width & height AFTER menu layout
            mw = overlay.width
            mh = overlay.height

            # 📍 Final position beside button
            final_x = bx - mw + dp(10)
            final_y = by - mh

            # Avoid offscreen
            final_x = max(dp(5), min(final_x, Window.width - mw - dp(5)))
            final_y = max(dp(5), min(final_y, Window.height - mh - dp(5)))

            overlay.pos = (final_x, final_y)

        except Exception as e:
            print("MENU POSITION ERROR:", e)

    def position_menu(self, card):
        try:
            if not self.menu or not self.menu.menu:
                return

            menu_widget = self.menu.menu  # actual dropdown
            btn = card.ids.p_menu_button

            # get button GLOBAL coordinates
            bx, by = btn.to_window(btn.x, btn.y)

            # adjust menu position (to the left of button)
            menu_widget.pos = (
                bx - menu_widget.width + dp(10),  # left/right
                by - menu_widget.height  # above/below
            )

        except Exception as e:
            print("Menu position error:", e)

    def open_privacy_menu(self, card):

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=(0, dp(16), 0, dp(16)),
            adaptive_height=True,
        )

        def add_item(label, value):
            btn = MDButton(
                style="text",
                on_release=lambda *a: (
                    self.privacy_menu.dismiss(),
                    self.change_post_audience(card, value)
                ),
            )
            btn.add_widget(MDButtonText(text=label))
            content.add_widget(btn)

        add_item("Public", "Public")
        add_item("Only Me", "Only Me")

        self.privacy_menu = MDDialog(
            MDDialogHeadlineText(text="Select Audience"),
            MDDialogContentContainer(content),
            auto_dismiss=True
        )

        self.privacy_menu.open()

    def pick_edit_image(self):
        from plyer import filechooser
        filechooser.open_file(on_selection=self.on_edit_image_selected)

    def detect_image_ext(self, img_bytes):
        try:
            from PIL import Image as PILImage
            img = PILImage.open(io.BytesIO(img_bytes))
            return img.format.lower()
        except Exception:
            return None

    def remove_edit_image(self):
        # mark image as removed
        self.edit_image_path = "__REMOVE__"

        # hide preview
        self.edit_preview.source = ""
        self.edit_preview.texture = None
        self.edit_preview.height = 0

    def edit_post(self, card):
        self.open_edit_post_dialog(card)

    def delete_post(self, card):
        if hasattr(self, "post_menu") and self.post_menu:
            self.post_menu.dismiss()

        if auth_tbl.delete_post(card.post_id):
            print("POST DELETED:", card.post_id)

            # remove card in UI
            if card.parent:
                card.parent.remove_widget(card)
        else:
            print("Failed to delete post")

    def change_post_audience(self, card, new_audience):

        # close privacy dialog safely
        if hasattr(self, "privacy_menu") and self.privacy_menu:
            self.privacy_menu.dismiss()

        post_id = card.post_id

        auth_tbl.update_post_audience(post_id, new_audience)

        # update icon in UI
        if new_audience == "Public":
            card.ids.p_audience_icon.icon = "earth"
        else:
            card.ids.p_audience_icon.icon = "lock"

        # ✅ SAME DESIGN PROMPT
        self.show_edit_snackbar(
            f"Post audience changed to {new_audience}"
        )

    def create_post_card(self, post):
        try:
            card = PostTemplate()  # ✅ THIS IS THE KEY

            # Fill fields
            card.ids.p_username.text = post["username"]
            card.ids.p_time.text = post["time"]
            card.ids.p_text.text = post["content"]

            # Store post id
            card.post_id = post["post_id"]
            post_owner = post["user_id"]

            current_user = self.current_user_id
            is_owner = str(current_user) == str(post_owner)

            # MENU VISIBILITY
            card.ids.p_menu_button.opacity = 1 if is_owner else 0
            card.ids.p_menu_button.disabled = not is_owner

            # Image
            if post.get("image"):
                card.ids.p_image.source = post["image"]
            else:
                card.ids.p_image.height = 0

            # Audience icon
            audience = post.get("audience", "public")
            card.ids.p_audience_icon.icon = "earth" if audience == "public" else "lock"

            return card

        except Exception as e:
            print("POST CARD ERROR:", e)
            return None

    def build(self):
        self.title = "Fitness Go"
        self.icon = "logo.png"
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Light"
        self.store = JsonStore("session.json")  # stay FROM HERE TO

        if self.store.exists("user"):
            self.current_user_id = self.store.get("user")["id"]
            self.current_user_name = self.store.get("user")["name"]  # HERE

        root = Builder.load_file("fitnessv2.kv")
        return root  # ★ no fade here (ScreenManager handles it)
#stay
    def run_migrations_once(self):
        """
        Automatically migrate exercises & articles ONCE per installation
        """
        if not self.store.exists("migrations_done"):
            print("🔁 Running initial data migrations...")

            migrate_exercises_json_to_db()
            migrate_json_to_db()

            self.store.put("migrations_done", done=True)
            print("✅ Migrations completed successfully")
        else:
            print("ℹ️ Migrations already completed")

    def on_start(self):

        # ✅ ALWAYS UPDATE LAST LOGIN
        self.update_last_login_if_logged_in()

        # ✅ RUN ARTICLES MIGRATION ONCE ONLY
        if not self.store.exists("migrations_done"):
            print("🔁 Running initial data migrations...")
            migrate_json_to_db()  # ✅ ARTICLES
            migrate_exercises_json_to_db()  # ✅ EXERCISES (if you want)
            self.store.put("migrations_done", done=True)
            print("✅ Migrations completed successfully")
        else:
            print("ℹ️ Migrations already completed")

        # ✅ CONTINUE NORMAL STARTUP FLOW
        if self.store.exists("user"):
            user = self.store.get("user")

            self.current_user_id = user.get("id")
            self.current_user_name = user.get("name")
            role = user.get("role")

            if role == "admin":
                self.root.current = "admin_dashboard_screen"
            else:
                self.root.current = "dashboard_screen"

            return

        # 🚪 NO SESSION
        self.root.current = "welcome_screen"

        welcome = self.root.get_screen("welcome_screen")
        welcome.opacity = 1
        welcome.ids.indicator.start()
        Clock.schedule_once(self.stop_loading_indicator, 1)

    def stop_loading_indicator(self, dt):
        welcome = self.root.get_screen("welcome_screen")
        welcome.ids.indicator.stop()
        Clock.schedule_once(self.fade_out_welcome, 1)

    def fade_out_welcome(self, dt):
        welcome = self.root.get_screen("welcome_screen")
        Animation(opacity=0, duration=1).start(welcome)
        Clock.schedule_once(lambda *x: self.switch_to_button_screen(), 1)

    def switch_to_button_screen(self):
        self.root.current = "button_screen"

    def open_saved_article(self, article):
        detail = self.root.get_screen("article_detail_screen")
        detail.origin_screen = "article_log_screen"

        detail.set_article(
            category=article.get("category", ""),
            title=article.get("title", ""),
            author=article.get("author", ""),
            date_str=article.get("date", ""),
            body_text=article.get("body", ""),
            image_source=article.get("image", "logo.png")
        )

        # Update bookmark icon state
        detail.check_if_saved()

        # Navigate to detail screen
        self.root.current = "article_detail_screen"

    def delete_saved_article(self, saved_id):
        success = auth_tbl.delete_saved_article(saved_id)

        if success:


            # reload saved list
            screen = self.root.get_screen("article_log_screen")
            screen.load_saved_articles()

            detail = self.root.get_screen("article_detail_screen")
            detail.check_if_saved()

    def save_article_from_detail(self):
        user_id = self.user_id
        if not user_id:
            return

        article = self.current_article
        if not article:
            return

        title = (article.get("title") or "").strip()
        if not title:
            return

        # ✅ Ask DB if it’s saved (returns SavedId or None)
        saved_id = auth_tbl.get_saved_article_id(user_id, title)

        if saved_id:
            # ❌ UNSAVE
            auth_tbl.delete_saved_article(saved_id)
            self.ids.save_btn.icon = "bookmark-outline"
        else:
            # ✅ SAVE
            auth_tbl.save_article(user_id, article)
            self.ids.save_btn.icon = "bookmark"

        # Optional: refresh article log if it’s open/exists
        try:
            log = self.manager.get_screen("article_log_screen")
            log.load_saved_articles()
        except Exception:
            pass

    def load_articles(self):
        container = self.ids.admin_wellness_container
        container.clear_widgets()

        rows = auth_tbl.get_all_articles()
        self.article_count = len(rows)

        if not rows:
            container.add_widget(
                MDLabel(
                    text="No articles yet. Click 'Add New' to create one.",
                    halign="center",
                    size_hint_y=None,
                    height=dp(50),
                )
            )
            return

        for row in rows:
            article = dict(row)

            img = article.get("image")

            if not img or not isinstance(img, str):
                article["image"] = "artipic_default.png"
            else:
                abs_img = os.path.join(BASE_DIR, img)
                if not os.path.exists(abs_img):
                    article["image"] = "artipic_default.png"

            card = Factory.AdminArticleCard(article=article)
            container.add_widget(card)

    def show_edit_snackbar(self, text):
        snack = MDSnackbar(
            MDSnackbarText(
                text=text,
                halign="center",
                valign="middle",
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="16sp"
            ),
            duration=2,
            size_hint=(0.9, None),
            height="50dp",
            pos_hint={"center_x": 0.5, "y": 0.02},  # lower position to avoid overlay
            md_bg_color=(0.8, 0.1, 0.1, 1),
            radius=[20, 20, 20, 20],
        )
        snack.open()


    #admin
    def on_resume(self):
        self.update_last_login_if_logged_in()

    def on_stop(self):
        self.update_last_login_if_logged_in()

    def update_last_login_if_logged_in(self):
        if hasattr(self, "current_user_id") and self.current_user_id:
            auth_tbl.update_last_login(self.current_user_id)

# ADDMOTO

    def logout(self):
        # Clear user session data
        self.current_user_id = None
        self.current_user_name = None

        # Clear persistent session
        if self.store and self.store.exists("user"):
            self.store.delete("user")

        # Reset the whole app UI
        self.reset_all()

    def open_admin_menu(self):
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.button import MDButton, MDButtonText
        from kivymd.uix.dialog import MDDialog, MDDialogContentContainer, MDDialogHeadlineText
        from kivy.metrics import dp

        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=(0, dp(16), 0, dp(16)),
            adaptive_height=True,
        )

        def add_item(label, callback):
            btn = MDButton(
                style="text",
                on_release=lambda *a: (
                    self.admin_menu.dismiss(),
                    callback()
                ),
            )
            btn.add_widget(MDButtonText(text=label))
            content.add_widget(btn)

        add_item("Admin Guidelines", self.open_admin_guidelines)
        add_item("Logout", self.logout)

        self.admin_menu = MDDialog(
            MDDialogHeadlineText(text="Admin Options"),
            MDDialogContentContainer(content),
            auto_dismiss=True
        )

        self.admin_menu.open()

    def open_admin_guidelines(self):

        text = (
            "[b]FitnessGo – Admin Guidelines for the Fitness Wall[/b]\n\n"

            "[b]1. Purpose of Administrative Access[/b]\n\n"
            "Administrative access is granted solely to maintain a safe, respectful, "
            "and fitness-focused environment within the Fitness Wall. Admin privileges "
            "must be exercised responsibly and only for moderation and system management purposes.\n\n"

            "[b]2. Ethical and Necessary Use of Access[/b]\n\n"
            "Administrators are granted visibility over all Fitness Wall posts, including "
            "both public and private content, strictly for moderation and system-related purposes. "
            "This access is necessary to properly review posts and determine whether content "
            "violates system rules.\n\n"

            "[b]3. Respect for User Privacy[/b]\n\n"
            "Although administrators may view all posts for moderation purposes, user content "
            "must still be treated as confidential. Access to private posts must not be abused "
            "and should only be exercised when required to fulfill moderation responsibilities.\n\n"

            "[b]4. Fair and Impartial Moderation[/b]\n\n"
            "Administrators are expected to review content objectively, avoid personal bias, "
            "and apply system rules consistently to all users. Moderation decisions must be based "
            "solely on established system guidelines and not on personal opinions or preferences.\n\n"

            "[b]5. Responsible Handling of Violations[/b]\n\n"
            "When inappropriate content is identified, the content must be verified as a violation. "
            "The post may be removed when necessary, and the violation must be properly recorded "
            "in the system. Repeated or serious violations are handled through system-defined processes.\n\n"

            "[b]6. System-Enforced Accountability[/b]\n\n"
            "The system automatically tracks user violations. Accounts that accumulate five (5) "
            "violations related to Fitness Wall activity are automatically deactivated to ensure "
            "fair and consistent enforcement.\n\n"

            "[b]7. Limitations of Admin Authority[/b]\n\n"
            "Administrators must respect the limitations of their role. They cannot edit user posts, "
            "cannot alter violation counts, and cannot bypass or override system rules. These "
            "limitations protect system integrity and fairness.\n\n"

            "[b]8. Accountability and Responsible Use[/b]\n\n"
            "Administrators are expected to act responsibly and remain accountable for their actions. "
            "Administrative access must be used strictly within the boundaries of system rules and "
            "ethical standards. Misuse of admin privileges may result in administrative review.\n\n"

            "[b]9. Professional Conduct[/b]\n\n"
            "Administrators are expected to maintain professional, respectful, and ethical behavior "
            "at all times. Any form of abuse, negligence, or misuse of administrative access is "
            "strictly prohibited.\n\n"

            "[b]10. Compliance with Guidelines[/b]\n\n"
            "All administrators are required to comply with these guidelines. Failure to do so may "
            "result in administrative review or removal of admin privileges."
        )

        label = MDLabel(
            text=text,
            markup=True,
            size_hint_y=None,
            text_size=(dp(300), None),
            padding=(dp(12), dp(12)),
        )
        label.bind(texture_size=label.setter("size"))

        scroll = MDScrollView(
            size_hint=(1, None),
            height=dp(300),  # 👈 controls dialog height
        )
        scroll.add_widget(label)

        self.guidelines_dialog = MDDialog(
            MDDialogHeadlineText(text="Admin Guidelines"),
            MDDialogContentContainer(scroll),
            auto_dismiss=True,
        )

        self.guidelines_dialog.open()


if __name__ == "__main__":
    #migrate_exercises_json_to_db()
    #migrate_json_to_db()
    FitnessApp().run()