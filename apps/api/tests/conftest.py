import os

# Valori finti: l'engine non si connette finché non serve, nessuna rete nei test.
os.environ.setdefault("NICEGUI_STORAGE_SECRET", "solo-per-i-test")
os.environ.setdefault("SUPABASE_URL", "https://prog.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
