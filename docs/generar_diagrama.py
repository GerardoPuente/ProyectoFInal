"""Genera docs/diagrama_arquitectura.png. Uso: python docs/generar_diagrama.py"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

fig, ax = plt.subplots(figsize=(13, 7.2), dpi=150)
ax.set_xlim(0, 13)
ax.set_ylim(0, 7.2)
ax.axis("off")


def caja(x, y, w, h, titulo, detalle="", fc="#ffffff", ec="#1f2937", lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h - 0.28, titulo, ha="center", va="center", fontsize=10.5, weight="bold", color="#111827")
    if detalle:
        ax.text(x + w / 2, y + h / 2 - 0.2, detalle, ha="center", va="center", fontsize=8, color="#374151", linespacing=1.4)


def flecha(a, b, texto="", rad=0.0, color="#1f2937", dy=0.0, dx=0.0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=13, lw=1.4, color=color,
                                 connectionstyle=f"arc3,rad={rad}"))
    if texto:
        ax.text((a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2 + dy, texto, ha="center", va="center", fontsize=7.6,
                color=color, bbox=dict(fc="white", ec="none", pad=1.2))


ax.text(6.5, 6.85, "ClipShare - arquitectura (Avance 2, entorno QA)", ha="center", fontsize=13.5, weight="bold")

# Usuario
caja(0.3, 3.2, 1.9, 1.3, "Navegador", "HTML plano\n(registro, login,\nsubir y ver clips)", fc="#f3f4f6")

# AWS / VPC
ax.add_patch(FancyBboxPatch((3.0, 0.45), 9.8, 5.7, boxstyle="round,pad=0.02,rounding_size=0.15",
                            fc="#fffbeb", ec="#b45309", lw=1.4, ls="--"))
ax.text(3.2, 0.7, "AWS Academy - us-east-1 (VPC por defecto)", fontsize=9, color="#92400e", weight="bold")

# EC2 + docker compose
ax.add_patch(FancyBboxPatch((3.3, 1.3), 4.0, 4.5, boxstyle="round,pad=0.02,rounding_size=0.12",
                            fc="#eff6ff", ec="#1d4ed8", lw=1.5))
ax.text(5.3, 5.5, "EC2 t3.small (SG: solo :8000 desde IP autorizada)", ha="center", fontsize=8.2, weight="bold", color="#1e3a8a")
ax.text(5.3, 5.2, "docker compose - rol LabInstanceProfile, sin llaves", ha="center", fontsize=7.6, color="#1e3a8a")
caja(3.6, 3.35, 3.4, 1.55, "Contenedor api", "FastAPI :8000\n/salud  /registro  /login  /clips", fc="#dbeafe", ec="#1d4ed8")
caja(3.6, 1.55, 3.4, 1.55, "Contenedor worker", "ffprobe: valida formato y duracion\nffmpeg: genera la miniatura", fc="#dbeafe", ec="#1d4ed8")

# S3 + KMS + RDS
caja(9.4, 4.3, 3.2, 1.5, "Amazon S3 (privado)", "clips/<usuario>/<id>/original.mp4\n.../miniatura.jpg\nacceso publico bloqueado + solo TLS",
     fc="#ecfdf5", ec="#047857")
caja(9.4, 2.9, 3.2, 0.95, "KMS (llave propia)", "cifra el bucket, rotacion anual", fc="#ecfdf5", ec="#047857")
caja(9.4, 1.0, 3.2, 1.55, "Amazon RDS PostgreSQL", "tablas usuarios y clips\ncifrado, sin acceso publico\nSG: 5432 solo desde la EC2",
     fc="#fef2f2", ec="#b91c1c")

# Flechas
flecha((2.2, 3.85), (3.6, 4.1), "HTTP :8000", dy=0.28, dx=-0.1)
flecha((7.0, 4.7), (9.4, 5.2), "1. sube el clip", dy=0.22, dx=-0.15)
flecha((7.0, 3.8), (9.4, 2.35), "2. registra el clip\n(estado 'pendiente')", color="#b91c1c", dx=0.35, dy=0.35)
flecha((7.0, 2.2), (9.4, 1.6), "3. toma 'pendiente' y\nactualiza el resultado", color="#b91c1c", dx=0.0, dy=-0.5)
flecha((7.0, 2.9), (9.4, 4.5), "4. descarga original\ny sube miniatura", rad=-0.12, dx=-0.35, dy=0.05)
flecha((11.0, 4.3), (11.0, 3.85), "", color="#047857")
flecha((11.0, 5.8), (1.25, 4.5), "5. URL firmada de 15 min: el navegador baja video y miniatura directo de S3",
       rad=0.17, color="#047857", dy=1.0)

ax.text(6.5, 0.12, "Pipeline (laptop / QA): Gitleaks, Bandit, pytest, Trivy fs / config / image, politica de Dockerfile, SBOM CycloneDX"
        " -> un solo veredicto BLOQUEADO / PERMITIDO", ha="center", fontsize=8, color="#374151")

destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagrama_arquitectura.png")
fig.savefig(destino, bbox_inches="tight", facecolor="white")
print("escrito", destino)
