"""
Rode este script UMA VEZ, depois de configurar a variável DATABASE_URL,
para cadastrar os funcionários iniciais.

No terminal do Railway (ou localmente com a env var configurada):
    python seed_employees.py
"""
from database import Base, engine, SessionLocal
import models

Base.metadata.create_all(bind=engine)

EMPLOYEES = [
    {"name": "Bruno Massard", "email": "bruno.massard@epiqglobal.com", "phone": "5521972909065"},
    {"name": "Yuri Medeiros", "email": "yuri.medeiros@epiqglobal.com", "phone": "5521993119964"},
    {"name": "Barbara Andrade", "email": "barbara.andrade@epiqglobal.com", "phone": "5511973202916"},
    {"name": "Andre Moreira", "email": "andre.moreira@epiqglobal.com", "phone": "5511963988841"},
    {"name": "Rafael Nakashima", "email": "rafael.nakashima@epiqglobal.com", "phone": "5511993933794"},
    {"name": "Thiago Casagrande", "email": "thiago.casagrande@epiqglobal.com", "phone": "5511987600685"},
]

db = SessionLocal()
for e in EMPLOYEES:
    exists = db.query(models.Employee).filter_by(email=e["email"]).first()
    if not exists:
        db.add(models.Employee(**e))
        print(f"Adicionado: {e['name']}")
    else:
        print(f"Já existe: {e['name']}")
db.commit()
db.close()
print("Concluído.")
