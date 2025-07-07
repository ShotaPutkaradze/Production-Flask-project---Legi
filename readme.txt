# Production Data Entry & Reporting System

## 1. Project Description

This is a web-based application built with **Flask** designed for a manufacturing facility to accurately log and manage production data. The system provides a streamlined, multi-step data entry process for operators and a comprehensive reporting and history-tracking interface for administrators.

The application is designed to be bilingual (Georgian/Russian) and supports multiple factories (e.g., Tbilisi and Kobuleti), each with distinct production lines categorized as "Wet" (სველი) and "Dry" (მშრალი).

---

## 2. Core Features

* **Role-Based Access Control:**
    * **Operator Role:** Can log in, enter new production data through a guided workflow, and view/edit their own submission history.
    * **Admin Role:** Has a global view of all records from all operators, access to a powerful reporting tool, and the ability to export data.

* **Guided Data Entry Workflow:** A multi-step process ensures data accuracy:
    1.  **Select Side:** Choose between "Wet" or "Dry" production lines.
    2.  **Select Subgroup:** Options are dynamically filtered based on the selected factory and side.
    3.  **Select Category:** Options are filtered based on the previously selected subgroup.
    4.  **Select Product & Enter Data:** The final step where operators select a specific product and enter quantities. The form fields adapt based on whether the "Wet" or "Dry" side was chosen.

* **Dynamic Data Filtering:** The application reads product nomenclature from a PostgreSQL database and dynamically filters the choices presented to the user at each step, preventing incorrect data combinations.

* **Reporting & History:**
    * **Paginated History:** Both operators and admins have access to a paginated history view to browse through records.
    * **Search Functionality:** All history pages include a live search bar to filter records.
    * **Date-Range Reporting:** A dedicated report page allows users (especially admins) to generate aggregated summaries of production data within a specific date range, with an additional filter for a specific operator.
    * **CSV Export:** Admins can export the entire production history to a CSV file.

* **Data Persistence:** All production records, edit history, and product nomenclature are stored in a **PostgreSQL** database.

---

## 3. Technology Stack

* **Backend:** Python, Flask
* **Database:** PostgreSQL
* **ORM:** Flask-SQLAlchemy
* **Frontend:** HTML, CSS, JavaScript
* **Libraries:** Pandas (used for the initial data import script)

---

## 4. Project Structure



/
|-- app.py # Main Flask application file with all routes and logic
|-- models.py # Defines the SQLAlchemy database models (Result, EditHistory, Nomenclature)
|-- config.py # Stores configuration variables (DB URI, Secret Key)
|-- requirements.txt # Python dependencies
|-- operators.csv # User credentials (username, password, factory)
|-- nomenclature.csv # Initial product data for import
|-- import_nomenclature.py # A one-time script to populate the 'nomenclature' table
|-- recreate_db.py # Utility script to drop and recreate database tables
|
|-- templates/
| |-- admin_history.html
| |-- operator_history.html
| |-- report.html
| |-- login.html
| |-- side.html
| |-- subgroup.html
| |-- category.html
| |-- product.html
| |-- submit.html
| |-- edit_result.html
| +-- ...
|
|-- logs/
| +-- app.log # Log file for errors and info messages
|
+-- venv/ # Virtual environment directory
---

## 5. Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <your-project-directory>
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    # For Windows
    python -m venv venv
    venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up PostgreSQL:**
    * Ensure you have a PostgreSQL server running.
    * Create a new database for the project (e.g., `production_db`).

5.  **Configure the Application:**
    * Create a `config.py` file in the root directory.
    * Add the following variables, replacing the placeholder values with your actual database credentials and a new secret key:
        ```python
        # config.py
        DB_USER = "your_db_user"
        DB_PASSWORD = "your_db_password"
        DB_HOST = "localhost"
        DB_NAME = "your_db_name"
        SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
        SECRET_KEY = "generate_a_new_strong_secret_key_here"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        ```

6.  **Prepare Data Files:**
    * Ensure `operators.csv` and `nomenclature.csv` are in the root directory and formatted correctly.

7.  **Create Database Tables and Import Data:**
    * Run the database recreation script **once** to create the tables according to `models.py`:
        ```bash
        python recreate_db.py
        ```
    * Run the import script **once** to populate the `nomenclature` table from your CSV file:
        ```bash
        python import_nomenclature.py
        ```

8.  **Run the Application:**
    ```bash
    flask run
    ```
    The application will be available at `http://127.0.0.1:5000`.

---

## 6. Future Improvements

* **Security:**
    * **Password Hashing:** The highest priority is to replace plaintext passwords in `operators.csv` with hashed passwords using `werkzeug.security`.
* **UI/UX Enhancements:**
    * Implement loading indicators for a smoother user experience during data filtering.
    * Improve the styling of `flash` messages for better user feedback.
    * Enhance visual cues for selected buttons (e.g., checkmarks).
* **Database Management:**
    * Integrate `Flask-Migrate` to handle future database schema changes gracefully without needing to recreate the database.
* **Code Structure:**
    * Refactor the application using Flask Blueprints to better organize routes and improve maintainability as the project grows.



