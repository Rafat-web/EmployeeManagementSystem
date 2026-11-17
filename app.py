from werkzeug.security import generate_password_hash
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from werkzeug.security import check_password_hash
from functools import wraps
from database import get_db_connection


app = Flask(__name__)
import os

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "employee-management-local-development-key"
)

# ==================================================
# ADMIN AUTHENTICATION DECORATOR
# ==================================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "admin_id" not in session:
            flash("Please login first.")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def index():

    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ==================================================
# ADMIN LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id, username, password_hash
                FROM admins
                WHERE username = %s
                """,
                (username,)
            )

            admin = cursor.fetchone()

            if admin and check_password_hash(
                admin["password_hash"], password
            ):

                session.clear()

                session["admin_id"] = admin["id"]
                session["admin_username"] = admin["username"]

                flash("Login successful!")

                return redirect(url_for("dashboard"))

            flash("Invalid username or password.")

        except Exception as e:

            print("LOGIN ERROR:", repr(e))
            flash("Unable to login. Please check the application error.")

        finally:

            if cursor is not None:
                cursor.close()

            if connection is not None and connection.is_connected():
                connection.close()

    return render_template("login.html")

@app.route("/profile", methods=["GET", "POST"])
@admin_required
def profile():

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                "SELECT * FROM admins WHERE id = %s",
                (session["admin_id"],)
            )
            admin = cursor.fetchone()

            if not check_password_hash(admin["password_hash"], current_password):
                flash("Current password is incorrect.")

            elif len(new_password) < 8:
                flash("New password must contain at least 8 characters.")

            elif new_password != confirm_password:
                flash("New passwords do not match.")

            else:
                new_hash = generate_password_hash(new_password)

                cursor.execute(
                    "UPDATE admins SET password_hash = %s WHERE id = %s",
                    (new_hash, session["admin_id"])
                )
                connection.commit()

                flash("Password changed successfully!")

        except Exception as e:
            print("PROFILE ERROR:", repr(e))
            flash("Unable to update password.")

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None and connection.is_connected():
                connection.close()

    return render_template(
        "profile.html",
        username=session.get("admin_username")
    )


# ==================================================
# ADMIN LOGOUT
# ==================================================

@app.route("/logout", methods=["POST"])
@admin_required
def logout():

    session.clear()

    flash("Logged out successfully!")

    return redirect(url_for("login"))


# ==================================================
# VIEW EMPLOYEES + SEARCH + FILTER
# ==================================================

@app.route("/employees")
@admin_required
def employees():

    search = request.args.get("search", "").strip()
    department = request.args.get("department", "").strip()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        query = "SELECT * FROM employees WHERE 1=1"
        values = []

        if search:

            query += " AND (name LIKE %s OR email LIKE %s)"

            values.extend([
                f"%{search}%",
                f"%{search}%"
            ])

        if department:

            query += " AND department = %s"
            values.append(department)

        query += " ORDER BY id DESC"

        cursor.execute(query, values)

        employee_list = cursor.fetchall()

        cursor.execute("""
            SELECT DISTINCT department
            FROM employees
            WHERE department IS NOT NULL
            AND department != ''
            ORDER BY department
        """)

        departments = cursor.fetchall()

    finally:

        cursor.close()
        connection.close()

    return render_template(
        "employees.html",
        employees=employee_list,
        departments=departments,
        search=search,
        selected_department=department
    )


# ==================================================
# ADD EMPLOYEE
# ==================================================


@app.route("/add", methods=["POST"])
@admin_required
def add_employee():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    designation = request.form.get("designation", "").strip()

    salary_input = request.form.get("salary", "").strip()
    joining_date = request.form.get("joining_date", "").strip() or None

    # Validate required fields
    if not name or not email:
        flash("Employee name and email are required.")
        return redirect(url_for("employees"))

    # Validate salary
    try:
        salary = float(salary_input) if salary_input else None

        if salary is not None and salary < 0:
            flash("Salary cannot be negative.")
            return redirect(url_for("employees"))

    except ValueError:
        flash("Please enter a valid salary.")
        return redirect(url_for("employees"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO employees
            (name, email, phone, department, designation, salary, joining_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            name,
            email,
            phone,
            department,
            designation,
            salary,
            joining_date
        ))

        connection.commit()
        flash("Employee added successfully!")

    except Exception as e:
        if connection is not None:
            connection.rollback()

        print("ADD EMPLOYEE ERROR:", repr(e))

        if getattr(e, "errno", None) == 1062:
            flash("This email address already exists.")
        else:
            flash("Unable to add employee. Please check the entered details.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return redirect(url_for("employees"))



# ==================================================
# DELETE EMPLOYEE
# ==================================================

@app.route("/delete/<int:id>", methods=["POST"])
@admin_required
def delete_employee(id):

    connection = get_db_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            "DELETE FROM employees WHERE id = %s",
            (id,)
        )

        connection.commit()

        flash("Employee deleted successfully!")

    except Exception as e:

        connection.rollback()

        print("DELETE EMPLOYEE ERROR:", repr(e))

        flash("Unable to delete employee.")

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("employees"))


# ==================================================
# EDIT EMPLOYEE
# ==================================================


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_employee(id):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            department = request.form.get("department", "").strip()
            designation = request.form.get("designation", "").strip()
            salary_input = request.form.get("salary", "").strip()
            joining_date = request.form.get("joining_date", "").strip() or None

            if not name or not email:
                flash("Employee name and email are required.")
                return redirect(url_for("edit_employee", id=id))

            try:
                salary = float(salary_input) if salary_input else None

                if salary is not None and salary < 0:
                    flash("Salary cannot be negative.")
                    return redirect(url_for("edit_employee", id=id))

            except ValueError:
                flash("Please enter a valid salary.")
                return redirect(url_for("edit_employee", id=id))

            cursor.execute("""
                UPDATE employees
                SET name=%s, email=%s, phone=%s,
                    department=%s, designation=%s,
                    salary=%s, joining_date=%s
                WHERE id=%s
            """, (
                name, email, phone, department,
                designation, salary, joining_date, id
            ))

            connection.commit()
            flash("Employee updated successfully!")
            return redirect(url_for("employees"))

        cursor.execute("SELECT * FROM employees WHERE id=%s", (id,))
        employee = cursor.fetchone()

        if employee is None:
            flash("Employee not found.")
            return redirect(url_for("employees"))

        return render_template("edit_employee.html", employee=employee)

    except Exception as e:
        if connection is not None:
            connection.rollback()

        print("EDIT EMPLOYEE ERROR:", repr(e))

        if getattr(e, "errno", None) == 1062:
            flash("This email address already exists.")
        else:
            flash("Unable to update employee. Please try again.")

        return redirect(url_for("edit_employee", id=id))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()



# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/dashboard")
@admin_required
def dashboard():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        # Total employees

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM employees
        """)

        total_employees = cursor.fetchone()["total"]

        # Total departments

        cursor.execute("""
            SELECT COUNT(DISTINCT department) AS total
            FROM employees
            WHERE department IS NOT NULL
            AND department != ''
        """)

        total_departments = cursor.fetchone()["total"]

        # Total salary

        cursor.execute("""
            SELECT COALESCE(SUM(salary), 0) AS total
            FROM employees
        """)

        total_salary = cursor.fetchone()["total"]

        # Recent employees

        cursor.execute("""
            SELECT *
            FROM employees
            ORDER BY id DESC
            LIMIT 5
        """)

        recent_employees = cursor.fetchall()

    finally:

        cursor.close()
        connection.close()

    return render_template(
        "dashboard.html",
        total_employees=total_employees,
        total_departments=total_departments,
        total_salary=total_salary,
        recent_employees=recent_employees
    )


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(debug=True)
