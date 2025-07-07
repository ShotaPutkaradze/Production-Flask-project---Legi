# production.py

from app import create_app

# Create an application instance using the factory from app/__init__.py
app = create_app()

if __name__ == '__main__':
    # Use debug=False for actual production, True for development
    app.run(debug=True)
