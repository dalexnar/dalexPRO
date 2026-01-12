"""Modelos de base de datos para DALEX."""

import json
from datetime import datetime
from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, 
    String, Text, Boolean, create_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from config.settings import config


class Base(DeclarativeBase):
    pass


# === MODELOS CORE (siempre activos) ===

class Sesion(Base):
    """Sesión de conversación."""
    __tablename__ = "sesiones"
    
    id = Column(String(36), primary_key=True)
    creada_en = Column(DateTime, default=datetime.utcnow)
    actualizada_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_json = Column(Text, default="{}")
    estado = Column(String(20), default="activa")
    
    mensajes = relationship("Mensaje", back_populates="sesion", cascade="all, delete-orphan")


class Mensaje(Base):
    """Mensaje en una sesión."""
    __tablename__ = "mensajes"
    
    id = Column(String(36), primary_key=True)
    sesion_id = Column(String(36), ForeignKey("sesiones.id"))
    rol = Column(String(20))
    contenido = Column(Text)
    creado_en = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(Text, default="{}")
    
    sesion = relationship("Sesion", back_populates="mensajes")


class RegistroAuditoria(Base):
    """Registro de auditoría."""
    __tablename__ = "auditoria"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sesion_id = Column(String(36), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    accion = Column(String(100))
    detalle_json = Column(Text, default="{}")
    duracion_ms = Column(Float, nullable=True)
    exito = Column(Integer, default=1)
    error = Column(Text, nullable=True)


# === MODELOS MEMORIA AVANZADA (solo modo pro) ===

class EpisodioMemoria(Base):
    """Registro de tareas ejecutadas (modo pro)."""
    __tablename__ = "memoria_episodica"
    
    id = Column(String(36), primary_key=True)
    sesion_id = Column(String(36), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    intencion = Column(Text)
    plan_id = Column(String(36))
    plan_resumen = Column(Text)
    total_pasos = Column(Integer)
    skills_usadas = Column(Text)  # JSON
    exito = Column(Boolean)
    respuesta_resumen = Column(Text)
    tiempo_total = Column(Float)
    pasos_autocorregidos = Column(Integer, default=0)
    errores_json = Column(Text, default="[]")


class RegistroErrorMemoria(Base):
    """Registro de errores para autocorrección (modo pro)."""
    __tablename__ = "memoria_errores"
    
    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    tipo_error = Column(String(100), index=True)
    mensaje_error = Column(Text)
    hash_error = Column(String(64), index=True)
    skill = Column(String(100), nullable=True)
    parametros_json = Column(Text, default="{}")
    estrategia_usada = Column(String(100), default="")
    solucion_exitosa = Column(Boolean, default=False)
    solucion_detalle_json = Column(Text, default="{}")
    ocurrencias = Column(Integer, default=1)


# === ENGINE Y SESSION ===

_engine = None
_SessionLocal = None


def get_engine():
    """Obtiene o crea el engine de SQLAlchemy."""
    global _engine
    if _engine is None:
        _engine = create_engine(config.database_url, echo=False)
    return _engine


def get_session():
    """Obtiene una nueva sesión de base de datos."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal()


def inicializar_base_datos():
    """Crea todas las tablas."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print("✓ Base de datos inicializada")
