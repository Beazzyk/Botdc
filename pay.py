from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from config_db import get_db_connection  # Importujemy funkcję połączenia z bazą danych

# Ładowanie zmiennych środowiskowych z .env
load_dotenv()

# Flask app initialization
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")
app.config["DISCORD_BOT_TOKEN"] = os.getenv("DISCORD_BOT_TOKEN")

discord = DiscordOAuth2Session(app)

YOUR_ADMIN_ID = 488756862976524291  # Zmień na swoje Discord ID jako admin (liczba)

# Funkcja do tworzenia tabeli w bazie (na początku, jeśli nie istnieje)
def create_tables():
    """Create the subscriptions table if it doesn't exist."""  
    conn = get_db_connection()
    if conn is None:
        return  # Zakończ, jeśli połączenie z bazą się nie powiodło
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id TEXT PRIMARY KEY,
            expires_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

# Sprawdzenie, czy użytkownik ma aktywną subskrypcję
def is_subscribed(user_id):
    """Check if a user has an active subscription."""
    conn = get_db_connection()
    if conn is None:
        return False  # Zwróć False, jeśli połączenie z bazą się nie powiodło
    cursor = conn.cursor()
    cursor.execute("SELECT expires_at FROM subscriptions WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        expires_at = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        return expires_at > datetime.now()
    return False

# Dodanie lub zaktualizowanie subskrypcji użytkownika
def add_subscription(user_id, days=30):
    """Add or update a user's subscription."""
    conn = get_db_connection()
    if conn is None:
        return  # Zakończ, jeśli połączenie z bazą nie powiodło się
    cursor = conn.cursor()
    expires_at = datetime.now() + timedelta(days=days)
    cursor.execute(
        """
        INSERT INTO subscriptions (user_id, expires_at)
        VALUES (%s, %s)
        ON CONFLICT(user_id)
        DO UPDATE SET expires_at = %s
        """,
        (user_id, expires_at.strftime("%Y-%m-%d %H:%M:%S"), expires_at.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

# Routes
@app.route("/login/")
def login():
    """Login route to start Discord OAuth2."""
    return discord.create_session(scope=["identify", "email"])

@app.route("/callback/")
def callback():
    """Handle Discord OAuth2 callback."""
    try:
        discord.callback()
        user = discord.fetch_user()
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    except Exception as e:
        return jsonify(error="Błąd logowania: " + str(e)), 400

@app.route("/logout/")
def logout():
    """Logout the user and clear the session."""
    discord.revoke()
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard/")
@requires_authorization
def dashboard():
    """Dashboard for both users and admins."""
    user = discord.fetch_user()
    if user.id == YOUR_ADMIN_ID:
        # Admin view
        conn = get_db_connection()
        if conn is None:
            return jsonify(error="Błąd połączenia z bazą danych"), 500
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subscriptions")
        subscriptions = cursor.fetchall()
        conn.close()
        return render_template("admin_dashboard.html", subscriptions=subscriptions)
    else:
        # User view
        active_subscription = is_subscribed(user.id)
        return render_template("user_dashboard.html", user=user, subscribed=active_subscription)

# Nowa trasa, która przekierowuje użytkownika na Patronite
@app.route("/redirect-to-patronite", methods=["POST"])
def redirect_to_patronite():
    patronite_url = "https://patronite.pl/Beazzy"  # Zmień na swój link Patronite
    return redirect(patronite_url)

# Error handling
@app.errorhandler(Unauthorized)
def unauthorized(e):
    return redirect(url_for("login"))

if __name__ == "__main__":
    create_tables()  # Tworzymy tabelę przy starcie aplikacji
    app.run(port=4242, debug=True)
