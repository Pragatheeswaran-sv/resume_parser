import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["SECRET_KEY"] = "dGVzdC1mZXJuZXQta2V5LWZvci1jaS11c2Utb25seQ=="