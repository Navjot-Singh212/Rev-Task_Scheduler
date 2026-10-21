import sqlite3

DB_NAME="scheduler.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def setup_database():
    conn=get_connection()
    cursor=conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            preferred_duration INTEGER NOT NULL,
            min_duration INTEGER NOT NULL,
            category TEXT NOT NULL,
            priority INTEGER NOT NULL,
            is_flexible BOOLEAN NOT NULL,
            is_hard_deadline BOOLEAN NOT NULL,
            scheduled_time TEXT,
            status TEXT DEFAULT 'pending'
            )
            """
    )

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_training_log(
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            energy_level INTEGER NOT NULL,
            time_of_day REAL NOT NULL,
            day_of_week INTEGER NOT NULL,
            completed INTEGER NOT NULL)""")
    conn.commit()
    conn.close()

def add_task(name,pref_dur,min_dur,category,priority,is_flex,is_hard,scheduled_time=None):
    #adds tasks to the table tasks
    conn=get_connection()
    cursor=conn.cursor()

    cursor.execute("""
        INSERT INTO tasks(task_name,preferred_duration,min_duration,category,priority,is_flexible,is_hard_deadline,scheduled_time)
        VALUES(?,?,?,?,?,?,?,?)""",
        (name,pref_dur,min_dur,category,priority,is_flex,is_hard,scheduled_time))

    conn.commit()
    conn.close()


def get_pending_tasks():
    #just to fetch the pending tasks for the day
    conn=get_connection()
    cursor=conn.cursor()

    cursor.execute("SELECT * FROM tasks WHERE status = 'pending'")
    tasks=cursor.fetchall()

    conn.close()
    return tasks


def mark_task_status(task_id,status,energy_level,time_of_day,day_of_week):
    conn=get_connection()
    cursor=conn.cursor()

    cursor.execute("UPDATE tasks SET status = ? WHERE id=?",(status,task_id))

    cursor.execute("SELECT category, preferred_duration FROM tasks WHERE id=?",(task_id,))
    task=cursor.fetchone()

    if task:
        category=task[0]
        duration=task[1]
        completed_flag=1 if status=="completed" else 0

        cursor.execute("""
            INSERT INTO ml_training_log (category,duration_minutes,energy_level,time_of_day,day_of_week,completed)
            VALUES (?,?,?,?,?,?)
          """,(category,duration,energy_level,time_of_day,day_of_week,completed_flag))

    conn.commit()
    conn.close()

def clear_all_tasks():
    conn=get_connection()
    cursor=conn.cursor()
    cursor.execute("DELETE FROM tasks")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='tasks' ")
    conn.commit()
    conn.close()



if __name__=="__main__":
    print("Setting up the database...")
    setup_database()
    print("Database created~")
    clear_all_tasks()

    print("Seeding fresh test tasks...")
    # add_task(name, pref_dur, min_dur, category, priority, is_flex, is_hard, scheduled_time)
    add_task("Study Java OOP", 120, 45, "learning", 5, True, False, None)
    add_task("Quick Code Review", 30, 15, "shallow_work", 3, True, False, None)
    add_task("Check Emails & Slacks", 15, 10, "admin", 2, True, False, None)
    add_task("Draft UI Wireframes", 60, 30, "creative", 4, True, False, None)
    add_task("Project Pitch Sync", 60, 60, "deep_work", 5, False, True, "18:00")  # Anchor
    add_task("Morning Standup", 15, 15, "admin", 3, False, True, "08:00")
    add_task("Team Architecture Sync", 45, 45, "deep_work", 5, False, True, "14:00")
    add_task("Refactor Database Schema", 90, 20, "deep_work", 4, True, False, None)
    print("\nPending tasks in database:")
    for t in get_pending_tasks():
        print(t)