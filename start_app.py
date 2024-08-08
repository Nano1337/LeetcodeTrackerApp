import datetime
import json
from typing import List, Dict, Any, Union
import csv
import os
from collections import defaultdict
import time
import random
import math
import sys
from colorama import init, Fore, Style
import subprocess
import tempfile

from generate_md import generate_md

# Initialize colorama
init(autoreset=True)

# Add this constant at the top of the file
SOLUTIONS_DIR = "solutions"

# Add this function to calculate review urgency
def calculate_urgency(review_date: datetime.date) -> str:
    days_until_review = (review_date - datetime.date.today()).days
    if days_until_review < 0:
        return "Overdue"
    elif days_until_review == 0:
        return "Today"
    elif days_until_review <= 2:
        return "Soon"
    else:
        return "Upcoming"

class Problem:
    def __init__(self, category: str, difficulty: str, name: str, status: str, link: str, notes: str = "", solutions: List[str] = None, markdown_file: str = ""):
        self.category = category
        self.difficulty = difficulty
        self.name = name
        self.status = status
        self.link = link
        self.notes = notes
        self.solutions = solutions or []
        self.markdown_file = markdown_file

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"Problem(name='{self.name}')"

class DailyLog:
    def __init__(self, date: Union[str, datetime.date], problem: Union[str, Problem], time_taken: int,
                 approach: str, challenges: str, solution: str):
        self.date = datetime.datetime.strptime(date, "%Y-%m-%d").date() if isinstance(date, str) else date
        self.problem = problem if isinstance(problem, Problem) else Problem(name=problem, category="", difficulty="", status="", link="")
        self.time_taken = time_taken
        self.approach = approach
        self.challenges = challenges
        self.solution = solution

class LeetCodeTracker:
    def __init__(self):
        self.daily_logs: List[DailyLog] = []
        self.neetcode150: List[Problem] = self.load_neetcode150()
        self.review_schedule: Dict[str, List[datetime.date]] = {}
        self.study_streak = 0
        self.last_study_date = None
        self.total_study_time = 0
        self.goals = {"problems_per_week": 5}

    def load_neetcode150(self) -> List[Problem]:
        problems = []
        try:
            with open('NeetCode 150 Personal List.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    problems.append(Problem(
                        category=row.get('Category', 'Uncategorized'),
                        difficulty=row.get('Difficulty', 'Unknown'),
                        name=row.get('Name', 'Unnamed Problem'),
                        status=row.get('Status', 'Unsolved'),
                        link=row.get('Link', ''),
                        notes=row.get('Notes ( Fill in with your method to solve )', '')
                    ))
        except FileNotFoundError:
            print(Fore.RED + "Error: 'NeetCode 150 Personal List.csv' file not found.")
            print("Please ensure the file is in the same directory as the script.")
            sys.exit(1)
        except csv.Error as e:
            print(Fore.RED + f"Error reading CSV file: {e}")
            sys.exit(1)
        
        if not problems:
            print(Fore.YELLOW + "Warning: No problems loaded from the CSV file.")
        
        return problems

    def add_daily_log(self, log: DailyLog):
        self.daily_logs.append(log)
        self.update_review_schedule(log.problem.name, log.date)
        self.update_problem_status(log.problem.name, "Completed")
        self.update_study_streak(log.date)
        self.total_study_time += log.time_taken

    def update_review_schedule(self, problem_name: str, solved_date: datetime.date):
        review_dates = [
            solved_date + datetime.timedelta(days=1),
            solved_date + datetime.timedelta(days=3),
            solved_date + datetime.timedelta(days=7),
            solved_date + datetime.timedelta(days=14),
            solved_date + datetime.timedelta(days=30)
        ]
        self.review_schedule[problem_name] = review_dates

    def update_problem_status(self, problem_name: str, status: str):
        for problem in self.neetcode150:
            if problem.name == problem_name:
                problem.status = status
                break

    def get_todays_spaced_repetition(self) -> List[Dict[str, Any]]:
        today = datetime.date.today()
        problems_to_review = []
        for problem, dates in self.review_schedule.items():
            for date in dates:
                if date <= today:
                    problem_obj = next((p for p in self.neetcode150 if p.name == problem), None)
                    if problem_obj:
                        problems_to_review.append({
                            "problem": problem_obj,
                            "urgency": calculate_urgency(date),
                            "review_date": date
                        })
                    break
        return problems_to_review

    def mark_problem_reviewed(self, problem: Problem, review_date: datetime.date):
        if problem.name in self.review_schedule:
            self.review_schedule[problem.name] = [d for d in self.review_schedule[problem.name] if d != review_date]
            if not self.review_schedule[problem.name]:
                del self.review_schedule[problem.name]
        
        # Add next review date
        next_review_date = datetime.date.today() + datetime.timedelta(days=7)  # You can adjust this interval
        if problem.name not in self.review_schedule:
            self.review_schedule[problem.name] = []
        self.review_schedule[problem.name].append(next_review_date)

    def get_next_problem(self) -> Problem:
        for problem in self.neetcode150:
            if problem.status != "Completed":
                return problem
        return None

    def get_random_problem(self) -> Problem:
        unsolved = [p for p in self.neetcode150 if p.status != "Completed"]
        return random.choice(unsolved) if unsolved else None

    def save_progress(self, filename: str):
        data = {
            "daily_logs": [{
                "date": log.date.isoformat() if isinstance(log.date, datetime.date) else log.date,
                "problem": log.problem.name if isinstance(log.problem, Problem) else log.problem,
                "time_taken": log.time_taken,
                "approach": log.approach,
                "challenges": log.challenges,
                "solution": log.solution
            } for log in self.daily_logs],
            "review_schedule": {k: [d.isoformat() for d in v] for k, v in self.review_schedule.items()},
            "neetcode150": [{**vars(problem), 'markdown_file': os.path.relpath(problem.markdown_file, SOLUTIONS_DIR) if problem.markdown_file else ''} for problem in self.neetcode150],
            "study_streak": self.study_streak,
            "last_study_date": self.last_study_date.isoformat() if self.last_study_date else None,
            "total_study_time": self.total_study_time,
            "goals": self.goals
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def load_progress(self, filename: str):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
            self.daily_logs = [DailyLog(**log) for log in data["daily_logs"]]
            self.review_schedule = {k: [datetime.date.fromisoformat(d) for d in v] for k, v in data["review_schedule"].items()}
            self.neetcode150 = []
            for problem_data in data["neetcode150"]:
                markdown_file = problem_data.pop('markdown_file', '')
                problem_data['markdown_file'] = os.path.join(SOLUTIONS_DIR, markdown_file) if markdown_file else ''
                self.neetcode150.append(Problem(**problem_data))
            self.study_streak = data["study_streak"]
            self.last_study_date = datetime.date.fromisoformat(data["last_study_date"]) if data["last_study_date"] else None
            self.total_study_time = data["total_study_time"]
            self.goals = data["goals"]

    def get_analytics(self) -> Dict:
        total_problems = len(self.neetcode150)
        completed_problems = sum(1 for problem in self.neetcode150 if problem.status == "Completed")
        completion_rate = (completed_problems / total_problems) * 100

        category_progress = defaultdict(lambda: {"total": 0, "completed": 0})
        difficulty_progress = defaultdict(lambda: {"total": 0, "completed": 0})
        for problem in self.neetcode150:
            category_progress[problem.category]["total"] += 1
            difficulty_progress[problem.difficulty]["total"] += 1
            if problem.status == "Completed":
                category_progress[problem.category]["completed"] += 1
                difficulty_progress[problem.difficulty]["completed"] += 1

        return {
            "total_problems": total_problems,
            "completed_problems": completed_problems,
            "completion_rate": completion_rate,
            "category_progress": dict(category_progress),
            "difficulty_progress": dict(difficulty_progress),
            "study_streak": self.study_streak,
            "total_study_time": self.total_study_time
        }

    def update_study_streak(self, study_date: datetime.date):
        if self.last_study_date is None or study_date - self.last_study_date == datetime.timedelta(days=1):
            self.study_streak += 1
        elif study_date != self.last_study_date:
            self.study_streak = 1
        self.last_study_date = study_date

    def search_problems(self, query: str) -> List[Problem]:
        # Get unique categories
        categories = sorted(set(problem.category for problem in self.neetcode150))
        
        if not categories:
            print(Fore.YELLOW + "No problem categories found.")
            return []

        print(Fore.CYAN + "\nProblem Categories:")
        for idx, category in enumerate(categories, 1):
            print(f"{idx}. {category}")
        print(f"{len(categories) + 1}. Search by name")

        while True:
            try:
                choice = int(input("\nEnter the number of your choice: "))
                if 1 <= choice <= len(categories):
                    selected_category = categories[choice - 1]
                    problems = [p for p in self.neetcode150 if p.category == selected_category]
                    break
                elif choice == len(categories) + 1:
                    query = input("Enter search query: ").lower()
                    problems = [p for p in self.neetcode150 if query in p.name.lower()]
                    break
                else:
                    print(Fore.RED + "Invalid choice. Please try again.")
            except ValueError:
                print(Fore.RED + "Invalid input. Please enter a number.")

        if not problems:
            print(Fore.YELLOW + "No matching problems found.")
            return []

        print(Fore.CYAN + f"\nFound {len(problems)} problems:")
        for idx, problem in enumerate(problems, 1):
            status_color = Fore.GREEN if problem.status == "Completed" else Fore.RED
            print(f"{idx}. {problem.name} - {status_color}{problem.status}{Style.RESET_ALL}")

        while True:
            try:
                problem_choice = int(input("\nEnter the number of the problem to view details (0 to exit): "))
                if 0 <= problem_choice <= len(problems):
                    break
                else:
                    print(Fore.RED + "Invalid choice. Please try again.")
            except ValueError:
                print(Fore.RED + "Invalid input. Please enter a number.")

        if problem_choice == 0:
            return []

        selected_problem = problems[problem_choice - 1]
        print(f"\nProblem: {Fore.CYAN}{selected_problem.name}{Style.RESET_ALL}")
        print(f"Category: {selected_problem.category}")
        print(f"Difficulty: {selected_problem.difficulty.capitalize()}")
        print(f"Status: {Fore.GREEN if selected_problem.status == 'Completed' else Fore.RED}{selected_problem.status}{Style.RESET_ALL}")
        print(f"Link: {Fore.BLUE}{selected_problem.link}{Style.RESET_ALL}")
        print(f"Notes: {selected_problem.notes}")
        return [selected_problem]

def print_menu():
    print(Fore.CYAN + "\nLeetCode Tracker Menu:")
    print(Fore.YELLOW + "1. Start Study Session and Log Progress")
    print(Fore.YELLOW + "2. Spaced Repetition")
    print(Fore.YELLOW + "3. View Analytics")
    print(Fore.YELLOW + "4. Edit Problem")
    print(Fore.YELLOW + "5. Set Goals")
    print(Fore.YELLOW + "6. Search Problems")
    print(Fore.YELLOW + "7. View Summary")
    print(Fore.YELLOW + "8. View History")
    print(Fore.RED + "9. Quit")

def start_study_session_and_log_progress(tracker: LeetCodeTracker):
    next_problem = tracker.get_next_problem()
    spaced_repetition_problems = tracker.get_todays_spaced_repetition()
    
    print(Fore.GREEN + "\nToday's study plan:")
    print(f"Next problem to solve: {Fore.CYAN}{next_problem.name}{Style.RESET_ALL} ({next_problem.category})")
    print(f"Link: {Fore.BLUE}{next_problem.link}{Style.RESET_ALL}")
    
    if spaced_repetition_problems:
        print(f"\nProblems for spaced repetition:")
        for problem in spaced_repetition_problems:
            urgency_color = Fore.RED if problem["urgency"] == "Overdue" else Fore.YELLOW if problem["urgency"] == "Today" else Fore.GREEN
            print(f"- {Fore.MAGENTA}{problem['problem'].name}{Style.RESET_ALL} ({problem['problem'].category}) - Urgency: {urgency_color}{problem['urgency']}{Style.RESET_ALL}")
    else:
        print(Fore.YELLOW + "\nNo problems for spaced repetition today.")

    input("\nPress Enter to start the study timer...")
    start_time = time.time()
    input("Press Enter when you're done studying...")
    end_time = time.time()
    study_time = int((end_time - start_time) / 60)
    print(f"\nYou studied for {Fore.GREEN}{study_time} minutes{Style.RESET_ALL}.")

    print(f"\nLogging progress for: {Fore.CYAN}{next_problem.name}{Style.RESET_ALL}")
    
    approach = input("Approach used (brief description): ")
    challenges = input("Challenges faced: ")
    
    # Open text editor for code input
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
        temp_file_name = temp_file.name
    
    editor = os.environ.get('EDITOR', 'nano')  # Use 'nano' as default if EDITOR is not set
    subprocess.call([editor, temp_file_name])
    
    with open(temp_file_name, 'r') as temp_file:
        solution_code = temp_file.read().strip()
    
    os.unlink(temp_file_name)  # Delete the temporary file
    
    # Generate Markdown file
    markdown_content = generate_md(next_problem, approach, challenges, solution_code)
    
     # Create solutions directory if it doesn't exist
    os.makedirs(SOLUTIONS_DIR, exist_ok=True)

    # Generate a filename for the markdown file
    markdown_filename = f"{next_problem.name.replace(' ', '_').lower()}.md"
    markdown_filepath = os.path.join(SOLUTIONS_DIR, markdown_filename)

    # Write the markdown content to the file
    with open(markdown_filepath, 'w') as md_file:
        md_file.write(markdown_content)

    # Update the problem's markdown_file attribute
    next_problem.markdown_file = markdown_filepath

    # Create and add the daily log
    log = DailyLog(
        date=datetime.date.today(),
        problem=next_problem,
        time_taken=study_time,
        approach=approach,
        challenges=challenges,
        solution=solution_code
    )
    tracker.add_daily_log(log)

    print(Fore.GREEN + f"\nProgress logged successfully. Markdown file created at: {markdown_filepath}")
    

def spaced_repetition_workflow(tracker: LeetCodeTracker):
    problems_to_review = tracker.get_todays_spaced_repetition()
    
    if not problems_to_review:
        print(Fore.YELLOW + "No problems for spaced repetition today.")
        return

    while problems_to_review:
        print(Fore.CYAN + "\nProblems for spaced repetition:")
        for idx, problem in enumerate(problems_to_review, 1):
            urgency_color = Fore.RED if problem["urgency"] == "Overdue" else Fore.YELLOW if problem["urgency"] == "Today" else Fore.GREEN
            print(f"{idx}. {Fore.MAGENTA}{problem['problem'].name}{Style.RESET_ALL} ({problem['problem'].category}) - Urgency: {urgency_color}{problem['urgency']}{Style.RESET_ALL}")

        choice = input("\nEnter the number of the problem to review (or 'q' to quit): ")
        if choice.lower() == 'q':
            break

        try:
            problem_index = int(choice) - 1
            if 0 <= problem_index < len(problems_to_review):
                selected_problem = problems_to_review[problem_index]
                review_problem(tracker, selected_problem['problem'], selected_problem['review_date'])
                problems_to_review.pop(problem_index)
            else:
                print(Fore.RED + "Invalid choice. Please try again.")
        except ValueError:
            print(Fore.RED + "Invalid input. Please enter a number or 'q'.")

def review_problem(tracker: LeetCodeTracker, problem: Problem, review_date: datetime.date):
    print(f"\nReviewing problem: {Fore.CYAN}{problem.name}{Style.RESET_ALL}")
    print(f"Category: {problem.category}")
    print(f"Difficulty: {problem.difficulty}")
    print(f"Link: {Fore.BLUE}{problem.link}{Style.RESET_ALL}")
    print(f"Current notes: {problem.notes}")

    if problem.markdown_file:
        print(f"Solution file: {problem.markdown_file}")
        open_file = input("Do you want to view the solution? (y/n): ").lower()
        if open_file == 'y':
            try:
                with open(problem.markdown_file, 'r') as md_file:
                    print(Fore.CYAN + "\n--- Solution ---")
                    print(Style.RESET_ALL + md_file.read())
                    print(Fore.CYAN + "--- End of Solution ---\n")
            except FileNotFoundError:
                print(Fore.RED + f"Error: File {problem.markdown_file} not found.")
            except IOError:
                print(Fore.RED + f"Error: Unable to read file {problem.markdown_file}.")

    action = input("\nChoose an action:\n1. Mark as reviewed\n2. Update solution and notes\n3. Skip\nEnter your choice (1-3): ")

    if action == '1':
        tracker.mark_problem_reviewed(problem, review_date)
        print(Fore.GREEN + "Problem marked as reviewed.")
    elif action == '2':
        # Rerun the complete logging workflow
        print(f"\nUpdating solution for: {Fore.CYAN}{problem.name}{Style.RESET_ALL}")
        
        approach = input("Approach used (brief description): ")
        challenges = input("Challenges faced: ")
        
        # Open text editor for code input
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
            temp_file_name = temp_file.name
        
        editor = os.environ.get('EDITOR', 'nano')  # Use 'nano' as default if EDITOR is not set
        subprocess.call([editor, temp_file_name])
        
        with open(temp_file_name, 'r') as temp_file:
            solution_code = temp_file.read().strip()
        
        os.unlink(temp_file_name)  # Delete the temporary file
        
        # Generate Markdown file
        markdown_content = generate_md(problem, approach, challenges, solution_code)
        
        # Update the markdown file
        if problem.markdown_file:
            with open(problem.markdown_file, 'w') as md_file:
                md_file.write(markdown_content)
        else:
            # If no markdown file exists, create a new one
            markdown_filename = f"{problem.name.replace(' ', '_').lower()}.md"
            markdown_filepath = os.path.join(SOLUTIONS_DIR, markdown_filename)
            with open(markdown_filepath, 'w') as md_file:
                md_file.write(markdown_content)
            problem.markdown_file = markdown_filepath

        # Update problem attributes
        problem.notes = approach
        problem.status = "Completed"

        # Mark as reviewed
        tracker.mark_problem_reviewed(problem, review_date)
        print(Fore.GREEN + "Solution updated and problem marked as reviewed.")
    elif action == '3':
        print(Fore.YELLOW + "Problem skipped.")
    else:
        print(Fore.RED + "Invalid choice. Problem skipped.")

def edit_problem(tracker: LeetCodeTracker):
    problems = tracker.search_problems("")
    if not problems:
        return

    selected_problem = problems[0]
    print(f"\nEditing problem: {Fore.CYAN}{selected_problem.name}{Style.RESET_ALL}")

    # Reuse the log progress workflow
    approach = input("Enter new approach (press Enter to keep current): ") or selected_problem.notes
    challenges = input("Enter new challenges faced: ")
    
    # Open text editor for code input
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
        temp_file_name = temp_file.name
        if selected_problem.markdown_file:
            with open(selected_problem.markdown_file, 'r') as md_file:
                temp_file.write(md_file.read())
    
    editor = os.environ.get('EDITOR', 'nano')
    subprocess.call([editor, temp_file_name])
    
    with open(temp_file_name, 'r') as temp_file:
        solution_code = temp_file.read().strip()
    
    os.unlink(temp_file_name)  # Delete the temporary file
    
    # Generate new Markdown file
    markdown_content = generate_md(selected_problem, approach, challenges, solution_code)
    
    # Update the markdown file
    if selected_problem.markdown_file:
        with open(selected_problem.markdown_file, 'w') as md_file:
            md_file.write(markdown_content)
    else:
        # If no markdown file exists, create a new one
        markdown_filename = f"{selected_problem.name.replace(' ', '_').lower()}.md"
        markdown_filepath = os.path.join(SOLUTIONS_DIR, markdown_filename)
        with open(markdown_filepath, 'w') as md_file:
            md_file.write(markdown_content)
        selected_problem.markdown_file = markdown_filepath

    # Update problem attributes
    selected_problem.notes = approach
    selected_problem.status = "Completed"

    print(Fore.GREEN + "Problem updated successfully!")

def set_goals(tracker: LeetCodeTracker):
    print(Fore.CYAN + "\nCurrent Goals:")
    print(f"Problems per week: {tracker.goals['problems_per_week']}")
    new_goal = input("Enter new weekly goal (press Enter to keep current): ")
    if new_goal:
        try:
            tracker.goals['problems_per_week'] = int(new_goal)
            print(Fore.GREEN + "Goal updated successfully!")
        except ValueError:
            print(Fore.RED + "Invalid input. Goal not updated.")

def view_summary(tracker: LeetCodeTracker):
    print(Fore.CYAN + "\nSummary:")
    
    # Weekly goal progress
    weekly_goal = tracker.goals['problems_per_week']
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    
    # Convert string dates to datetime.date objects
    problems_this_week = sum(1 for log in tracker.daily_logs if start_of_week <= (datetime.datetime.strptime(log.date, "%Y-%m-%d").date() if isinstance(log.date, str) else log.date) <= today)
    
    print(f"Weekly Goal: {problems_this_week}/{weekly_goal} problems solved")
    
    # Recent activity
    print("\nRecent Activity:")
    recent_logs = sorted(tracker.daily_logs, key=lambda x: datetime.datetime.strptime(x.date, "%Y-%m-%d").date() if isinstance(x.date, str) else x.date, reverse=True)[:5]
    for log in recent_logs:
        log_date = datetime.datetime.strptime(log.date, "%Y-%m-%d").date() if isinstance(log.date, str) else log.date
        problem_name = str(log.problem) if isinstance(log.problem, Problem) else log.problem
        print(f"{log_date}: Solved {problem_name} ({log.time_taken} minutes)")
    
    # Overall progress
    total_problems = len(tracker.neetcode150)
    completed_problems = sum(1 for problem in tracker.neetcode150 if problem.status == "Completed")
    completion_rate = (completed_problems / total_problems) * 100
    print(f"\nOverall Progress: {completed_problems}/{total_problems} ({completion_rate:.2f}%)")
    
def view_analytics(tracker: LeetCodeTracker):
    analytics = tracker.get_analytics()
    
    print(Fore.CYAN + "\nLeetCode Tracker Analytics:")
    print(f"Total problems: {analytics['total_problems']}")
    print(f"Completed problems: {analytics['completed_problems']}")
    print(f"Completion rate: {analytics['completion_rate']:.2f}%")
    print(f"Study streak: {analytics['study_streak']} days")
    print(f"Total study time: {analytics['total_study_time']} minutes")

    print(Fore.YELLOW + "\nCategory Progress:")
    for category, progress in analytics['category_progress'].items():
        completion_rate = (progress['completed'] / progress['total']) * 100
        print(f"{category}: {progress['completed']}/{progress['total']} ({completion_rate:.2f}%)")

    print(Fore.YELLOW + "\nDifficulty Progress:")
    for difficulty, progress in analytics['difficulty_progress'].items():
        completion_rate = (progress['completed'] / progress['total']) * 100
        print(f"{difficulty}: {progress['completed']}/{progress['total']} ({completion_rate:.2f}%)")

def view_history(tracker: LeetCodeTracker):
    print(Fore.CYAN + "\nProblem Solving History:")
    logs = sorted(tracker.daily_logs, key=lambda x: x.date, reverse=True)
    
    limit = input("Enter the number of entries to view (press Enter for default 10): ")
    try:
        limit = int(limit) if limit else 10
    except ValueError:
        print(Fore.RED + "Invalid input. Using default limit of 10.")
        limit = 10
    
    for log in logs[:limit]:
        log_date = log.date if isinstance(log.date, datetime.date) else datetime.datetime.strptime(log.date, "%Y-%m-%d").date()
        problem_name = log.problem.name if isinstance(log.problem, Problem) else log.problem
        print(f"{log_date}: {problem_name} - {log.time_taken} minutes")

def main():
    tracker = LeetCodeTracker()
    tracker.load_progress("leetcode_progress.json")

    while True:
        print_menu()
        choice = input("Enter your choice (1-9): ")

        if choice == '1':
            start_study_session_and_log_progress(tracker)
            tracker.save_progress("leetcode_progress.json")
            tracker.load_progress("leetcode_progress.json")
        elif choice == '2':
            tracker.load_progress("leetcode_progress.json")
            spaced_repetition_workflow(tracker)
            tracker.save_progress("leetcode_progress.json")
        elif choice == '3':
            tracker.load_progress("leetcode_progress.json")
            view_analytics(tracker)
        elif choice == '4':
            tracker.load_progress("leetcode_progress.json")
            edit_problem(tracker)
            tracker.save_progress("leetcode_progress.json")
        elif choice == '5':
            set_goals(tracker)
            tracker.save_progress("leetcode_progress.json")
            tracker.load_progress("leetcode_progress.json")
        elif choice == '6':
            tracker.load_progress("leetcode_progress.json")
            tracker.search_problems("")
        elif choice == '7':
            tracker.load_progress("leetcode_progress.json")
            view_summary(tracker)
        elif choice == '8':
            tracker.load_progress("leetcode_progress.json")
            view_history(tracker)
        elif choice == '9':
            print(Fore.YELLOW + "Thank you for using LeetCode Tracker. Happy coding!")
            break
        else:
            print(Fore.RED + "Invalid choice. Please try again.")
        
        tracker.save_progress("leetcode_progress.json")

if __name__ == "__main__":
    main()
