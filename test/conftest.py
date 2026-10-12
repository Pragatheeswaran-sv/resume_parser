import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["SECRET_KEY"] = "lw2NJ2Eedo0F8v3Z1hjqH3FZDnwMuF4fbYGW65l1P9k="