from flask import Flask, request, jsonify
import mysql.connector
import datetime
import threading
import tkinter as tk
import ctypes
import win32gui, win32con
import signal
import sys
import logging
import cv2
from PIL import Image, ImageTk
import pygetwindow as gw
from pywinauto import Application, Desktop

app = Flask(__name__)

# Configure MySQL connection
db_config = {
    'user': 'root',
    'password': '@Anshika1234',
    'host': '127.0.0.1',
    'database': 'your_database'
}

# Configure logging
logging.basicConfig(level=logging.INFO)

# Global variable to hold the reference to the root window
root = None

# Function to disable taskbar
def disable_taskbar():
    hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

# Function to enable taskbar
def enable_taskbar():
    hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

# Function to disable Alt+Tab and Windows keys
def disable_alt_tab():
    ctypes.windll.user32.SystemParametersInfoW(97, 0, 0, 0)

# Function to enable Alt+Tab and Windows keys
def enable_alt_tab():
    ctypes.windll.user32.SystemParametersInfoW(97, 1, 0, 0)

# Function to enforce fullscreen and bring the interview window to the front
def enforce_fullscreen():
    while True:
        try:
            interview_window = gw.getWindowsWithTitle('Interview Screen')[0]
            interview_window.activate()
            interview_window.maximize()
        except Exception as e:
            logging.error(f"Error enforcing fullscreen: {e}")
        finally:
            # Sleep for a short period before checking again
            time.sleep(1) # type: ignore

# Function to run the interview screen
def run_interview_screen():
    global root
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.title("Interview Screen")
    root.resizable(False, False)  # Disable window resizing

    disable_alt_tab()
    disable_taskbar()

    def on_closing():
        enable_alt_tab()
        enable_taskbar()
        root.destroy()

    root.bind("<Escape>", lambda e: on_closing())
    root.protocol("WM_DELETE_WINDOW", on_closing)

    label = tk.Label(root, text="Interview Screen", font=("Helvetica", 32))
    label.pack(expand=True)

    # Create a new Label widget to display the video feed
    video_label = tk.Label(root)
    video_label.pack()

    # Create a new OpenCV video capture object
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        logging.error("Cannot open default camera")
        return

    def update_video_feed():
        ret, frame = cap.read()
        if ret:
            # Convert the OpenCV image to a format that can be displayed in a Tkinter Label widget
            cv2_im = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2_im)
            imgtk = ImageTk.PhotoImage(image=img)
            video_label.config(image=imgtk)
            video_label.image = imgtk
        else:
            logging.error("Cannot read video feed")
            return
        root.after(10, update_video_feed)

    update_video_feed()

    # Start the fullscreen enforcement in a separate thread
    threading.Thread(target=enforce_fullscreen, daemon=True).start()

    root.mainloop()

# Route to start the interview test
@app.route('/start-test', methods=['POST'])
def start_test():
    data = request.get_json()

    # Start the interview screen in a new thread
    threading.Thread(target=run_interview_screen).start()

    # Create a new test document in the database
    test = {
        "userId": data['userId'],
        "testId": data['testId'],
        "startedAt": datetime.datetime.utcnow(),
        "terminated": False
    }

    # Insert into MySQL database
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO tests (userId, testId, startedAt, terminated)
            VALUES (%s, %s, %s, %s)
        """, (test['userId'], test['testId'], test['startedAt'], test['terminated']))
        connection.commit()
        logging.info("Test started successfully")
    except mysql.connector.Error as err:
        logging.error(f"Database error: {err}")
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

    return jsonify({"message": "Test started successfully"})

# Route to terminate the interview test
@app.route('/terminate-test', methods=['POST'])
def terminate_test():
    data = request.get_json()
    user_id = data.get('userId')
    test_id = data.get('testId')

    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM tests WHERE userId = %s AND testId = %s
        """, (user_id, test_id))
        test = cursor.fetchone()
        if test is None:
            return jsonify({'error': 'Test not found'}), 404

        cursor.execute("""
            UPDATE tests SET terminated = %s WHERE id = %s
        """, (True, test['id']))
        connection.commit()
        logging.info("Test terminated successfully")
    except mysql.connector.Error as err:
        logging.error(f"Database error: {str(err)}")
        return jsonify({"error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

    # Release restrictions
    enable_taskbar()
    enable_alt_tab()

    # Close the fullscreen application
    if root is not None:
        root.destroy()

    return jsonify({"message": "Test terminated successfully"})

if __name__ == "__main__":
    app.run(debug=True)
