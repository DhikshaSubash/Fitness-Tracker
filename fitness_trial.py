import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import matplotlib.pyplot as plt

class User:
    def __init__(self, username, password, name='', age=0, gender='', weight=0, height=0):
        self.username = username
        self.password = password
        self.name = name
        self.age = age
        self.gender = gender
        self.weight = weight
        self.height = height

class FoodItem:
    def __init__(self, name, protein, carbohydrates, fats, fiber):
        self.name = name
        self.protein = protein
        self.carbohydrates = carbohydrates
        self.fats = fats
        self.fiber = fiber

class Workout:
    def __init__(self, name, calories_burned):
        self.name = name
        self.calories_burned = calories_burned

class FitnessTracker:
    def __init__(self):
        self.food_items = []
        self.workouts = []
        self.calories_consumed = 0
        self.calories_burned = 0

    def add_food_item(self, food_item):
        self.food_items.append(food_item)
        self.calories_consumed += (food_item.protein * 4 + food_item.carbohydrates * 4 + food_item.fats * 9)

    def add_workout(self, workout):
        self.workouts.append(workout)
        self.calories_burned += workout.calories_burned

    def plot_progress(self):
        labels = ['Calories Consumed', 'Calories Burned']
        values = [self.calories_consumed, self.calories_burned]

        plt.bar(labels, values)
        plt.title('Fitness Progress')
        plt.xlabel('Metrics')
        plt.ylabel('Calories')
        plt.show()

class FitnessGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Fitness Tracker')

        self.tracker = FitnessTracker()
        self.current_user = None

        self.frame = ttk.Frame(root)
        self.frame.pack(padx=20, pady=20)

        self.username_label = ttk.Label(self.frame, text='Username:')
        self.username_label.grid(row=0, column=0, padx=5, pady=5)
        self.username_entry = ttk.Entry(self.frame)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        self.password_label = ttk.Label(self.frame, text='Password:')
        self.password_label.grid(row=1, column=0, padx=5, pady=5)
        self.password_entry = ttk.Entry(self.frame, show='*')
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        self.login_button = ttk.Button(self.frame, text='Login', command=self.login)
        self.login_button.grid(row=2, columnspan=2, padx=5, pady=5)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showerror('Login Failed', 'Please enter both username and password.')
            return

        if self.check_credentials(username, password):
            self.current_user = User(username, password)
            messagebox.showinfo('Login Successful', f'Welcome, {self.current_user.username}!')
            self.show_tracker()
        else:
            messagebox.showerror('Login Failed', 'Incorrect username or password.')

    def check_credentials(self, username, password):
        with open('user_data.csv', 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['username'] == username and row['password'] == password:
                    return True
        return False

    def show_tracker(self):
        self.frame.destroy()
        self.frame = ttk.Frame(self.root)
        self.frame.pack(padx=20, pady=20)

        user_info_label = ttk.Label(self.frame, text=f'Logged in as: {self.current_user.username}')
        user_info_label.grid(row=0, columnspan=2, padx=5, pady=5)

        self.food_label = ttk.Label(self.frame, text='Food Item:')
        self.food_label.grid(row=1, column=0, padx=5, pady=5)
        self.food_combo = ttk.Combobox(self.frame, values=['Apple', 'Banana', 'Chicken Breast'])
        self.food_combo.grid(row=1, column=1, padx=5, pady=5)

        self.workout_label = ttk.Label(self.frame, text='Workout:')
        self.workout_label.grid(row=2, column=0, padx=5, pady=5)
        self.workout_combo = ttk.Combobox(self.frame, values=['Running', 'Cycling', 'Swimming'])
        self.workout_combo.grid(row=2, column=1, padx=5, pady=5)

        self.add_food_button = ttk.Button(self.frame, text='Add Food', command=self.open_add_food_window)
        self.add_food_button.grid(row=3, column=0, padx=5, pady=5)

        self.add_workout_button = ttk.Button(self.frame, text='Add Workout', command=self.open_add_workout_window)
        self.add_workout_button.grid(row=3, column=1, padx=5, pady=5)

        self.plot_button = ttk.Button(self.frame, text='Plot Progress', command=self.plot_progress)
        self.plot_button.grid(row=4, columnspan=2, padx=5, pady=5)

    def open_add_food_window(self):
        add_food_window = AddFoodWindow(self.root, self.tracker)

    def open_add_workout_window(self):
        add_workout_window = AddWorkoutWindow(self.root, self.tracker)

    def plot_progress(self):
        self.tracker.plot_progress()

class AddFoodWindow:
    def __init__(self, parent, tracker):
        self.parent = parent
        self.tracker = tracker
        self.window = tk.Toplevel(parent)
        self.window.title('Add Food')

        self.frame = ttk.Frame(self.window)
        self.frame.pack(padx=20, pady=20)

        self.food_label = ttk.Label(self.frame, text='Food Name:')
        self.food_label.grid(row=0, column=0, padx=5, pady=5)
        self.food_entry = ttk.Entry(self.frame)
        self.food_entry.grid(row=0, column=1, padx=5, pady=5)

        self.protein_label = ttk.Label(self.frame, text='Protein (g):')
        self.protein_label.grid(row=1, column=0, padx=5, pady=5)
        self.protein_entry = ttk.Entry(self.frame)
        self.protein_entry.grid(row=1, column=1, padx=5, pady=5)

        self.carbs_label = ttk.Label(self.frame, text='Carbohydrates (g):')
        self.carbs_label.grid(row=2, column=0, padx=5, pady=5)
        self.carbs_entry = ttk.Entry(self.frame)
        self.carbs_entry.grid(row=2, column=1, padx=5, pady=5)

        self.fats_label = ttk.Label(self.frame, text='Fats (g):')
        self.fats_label.grid(row=3, column=0, padx=5, pady=5)
        self.fats_entry = ttk.Entry(self.frame)
        self.fats_entry.grid(row=3, column=1, padx=5, pady=5)

        self.fiber_label = ttk.Label(self.frame, text='Fiber (g):')
        self.fiber_label.grid(row=4, column=0, padx=5, pady=5)
        self.fiber_entry = ttk.Entry(self.frame)
        self.fiber_entry.grid(row=4, column=1, padx=5, pady=5)

        self.add_button = ttk.Button(self.frame, text='Add', command=self.add_food)
        self.add_button.grid(row=5, columnspan=2, padx=5, pady=5)

    def add_food(self):
        name = self.food_entry.get()
        protein = float(self.protein_entry.get())
        carbs = float(self.carbs_entry.get())
        fats = float(self.fats_entry.get())
        fiber = float(self.fiber_entry.get())

        food_item = FoodItem(name, protein, carbs, fats, fiber)
        self.tracker.add_food_item(food_item)
        messagebox.showinfo('Food Added', 'Food item added successfully.')
        self.window.destroy()

class AddWorkoutWindow:
    def __init__(self, parent, tracker):
        self.parent = parent
        self.tracker = tracker
        self.window = tk.Toplevel(parent)
        self.window.title('Add Workout')

        self.frame = ttk.Frame(self.window)
        self.frame.pack(padx=20, pady=20)

        self.workout_label = ttk.Label(self.frame, text='Workout Name:')
        self.workout_label.grid(row=0, column=0, padx=5, pady=5)
        self.workout_entry = ttk.Entry(self.frame)
        self.workout_entry.grid(row=0, column=1, padx=5, pady=5)

        self.calories_label = ttk.Label(self.frame, text='Calories Burned:')
        self.calories_label.grid(row=1, column=0, padx=5, pady=5)
        self.calories_entry = ttk.Entry(self.frame)
        self.calories_entry.grid(row=1, column=1, padx=5, pady=5)

        self.add_button = ttk.Button(self.frame, text='Add', command=self.add_workout)
        self.add_button.grid(row=2, columnspan=2, padx=5, pady=5)

    def add_workout(self):
        name = self.workout_entry.get()
        calories_burned = float(self.calories_entry.get())

        workout = Workout(name, calories_burned)
        self.tracker.add_workout(workout)
        messagebox.showinfo('Workout Added', 'Workout added successfully.')
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FitnessGUI(root)
    root.mainloop()
