"""Génère un récapitulatif PDF en français du système Alltrucks AMCAT.

Format : 3 pages (couverture + 2 pages de contenu),
ton business, design aux couleurs Alltrucks
(light blue #01B5E2 + dark blue #0D47A1).
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    ListFlowable, ListItem, Image,
)


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
OUTPUT = SCRIPT_DIR / 'alltrucks_amcat_recap_fr.pdf'
LOGO_PATH = BASE_DIR / 'static' / 'img' / 'logo.png'

# Palette Alltrucks
LIGHT_BLUE = colors.HexColor('#01B5E2')
DARK_BLUE = colors.HexColor('#00193E')
DEEP_BLUE = colors.HexColor('#000F26')
NAVY = colors.HexColor('#1A1A2E')
ACCENT_BG = colors.HexColor('#E3F2FD')
PALE_BG = colors.HexColor('#F4FAFD')
GREY_MID = colors.HexColor('#888888')
GREY_LIGHT = colors.HexColor('#E1E5EA')

PAGE_WIDTH, PAGE_HEIGHT = A4


def _draw_top_band(canvas):
    canvas.setFillColor(LIGHT_BLUE)
    canvas.rect(0, PAGE_HEIGHT - 0.5*cm, PAGE_WIDTH, 0.5*cm, stroke=0, fill=1)


def _draw_bottom_band(canvas):
    canvas.setFillColor(DARK_BLUE)
    canvas.rect(0, 0, PAGE_WIDTH, 0.3*cm, stroke=0, fill=1)


def page_chrome(canvas, doc):
    canvas.saveState()
    _draw_top_band(canvas)
    _draw_bottom_band(canvas)
    canvas.setFillColor(NAVY)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(1.5*cm, 0.5*cm, 'Alltrucks AMCAT — Assistant hotline IA')
    canvas.drawRightString(PAGE_WIDTH - 1.5*cm, 0.5*cm, f'Page {doc.page}')
    canvas.restoreState()


def cover_chrome(canvas, doc):
    """Couverture pleine page : grand bloc dégradé + logo + titre."""
    canvas.saveState()

    # Bandeau dark-blue qui couvre 60 % de la page
    canvas.setFillColor(DARK_BLUE)
    canvas.rect(0, PAGE_HEIGHT * 0.40, PAGE_WIDTH, PAGE_HEIGHT * 0.60, stroke=0, fill=1)

    # Bande light-blue épaisse, signature Alltrucks
    canvas.setFillColor(LIGHT_BLUE)
    canvas.rect(0, PAGE_HEIGHT * 0.36, PAGE_WIDTH, 0.6*cm, stroke=0, fill=1)

    # Bloc de couleur très claire (bleu lavande) pour le bas de page
    canvas.setFillColor(PALE_BG)
    canvas.rect(0, 0.3*cm, PAGE_WIDTH, PAGE_HEIGHT * 0.36 - 0.3*cm, stroke=0, fill=1)

    # Cercles décoratifs (motif géométrique discret en haut à droite)
    canvas.setFillColor(LIGHT_BLUE)
    canvas.setFillAlpha(0.18)
    canvas.circle(PAGE_WIDTH - 2*cm, PAGE_HEIGHT - 5.5*cm, 3.5*cm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFillAlpha(0.10)
    canvas.circle(PAGE_WIDTH - 5*cm, PAGE_HEIGHT - 9*cm, 2.2*cm, stroke=0, fill=1)
    canvas.setFillAlpha(1)

    # Logo en blanc en haut à gauche
    if LOGO_PATH.exists():
        try:
            canvas.drawImage(str(LOGO_PATH), 1.8*cm, PAGE_HEIGHT - 3*cm,
                             width=4.5*cm, height=1.6*cm, mask='auto',
                             preserveAspectRatio=True)
        except Exception:
            pass

    # Titres en blanc dans le bloc
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 38)
    canvas.drawString(1.8*cm, PAGE_HEIGHT * 0.55, 'AMCAT')
    canvas.setFont('Helvetica-Bold', 18)
    canvas.drawString(1.8*cm, PAGE_HEIGHT * 0.50, 'Assistant hotline IA')

    canvas.setFillColor(ACCENT_BG)
    canvas.setFont('Helvetica', 11)
    canvas.drawString(1.8*cm, PAGE_HEIGHT * 0.46, 'Diagnostic instantané · Multilingue · Capitalisation des cas historiques')

    # Pied
    canvas.setFillColor(DARK_BLUE)
    canvas.rect(0, 0, PAGE_WIDTH, 0.3*cm, stroke=0, fill=1)
    canvas.setFillColor(NAVY)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(1.8*cm, 0.5*cm, 'Document interne · usage Alltrucks')
    canvas.drawRightString(PAGE_WIDTH - 1.8*cm, 0.5*cm, 'Récapitulatif fonctionnel · 2026')

    canvas.restoreState()


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SubTitle', parent=styles['Heading2'],
        fontSize=13, leading=17, spaceBefore=8, spaceAfter=4,
        textColor=DARK_BLUE, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='SubSubTitle', parent=styles['Heading3'],
        fontSize=10, leading=13, spaceBefore=6, spaceAfter=2,
        textColor=LIGHT_BLUE, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Body2', parent=styles['BodyText'],
        fontSize=9.5, leading=13, alignment=TA_JUSTIFY, textColor=NAVY,
        spaceAfter=4))
    styles.add(ParagraphStyle(name='Bullet2', parent=styles['BodyText'],
        fontSize=9.5, leading=13, leftIndent=12, bulletIndent=2,
        textColor=NAVY, spaceAfter=3))
    styles.add(ParagraphStyle(name='Caption2', parent=styles['BodyText'],
        fontSize=8, leading=10, textColor=GREY_MID, spaceAfter=2,
        fontName='Helvetica-Oblique'))
    styles.add(ParagraphStyle(name='Callout', parent=styles['BodyText'],
        fontSize=10, leading=14, alignment=TA_JUSTIFY, textColor=DARK_BLUE,
        spaceAfter=4))
    return styles


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(t, style), bulletColor=LIGHT_BLUE) for t in items],
        bulletType='bullet', start='•', leftIndent=12,
    )


def kv_table(rows):
    t = Table(rows, colWidths=[5*cm, 11.5*cm], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 0), (0, -1), DARK_BLUE),
        ('TEXTCOLOR', (1, 0), (1, -1), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), PALE_BG),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, GREY_LIGHT),
        ('LINEBEFORE', (0, 0), (0, -1), 2.5, LIGHT_BLUE),
    ]))
    return t


def callout(text, styles):
    p = Paragraph(text, styles['Callout'])
    t = Table([[p]], colWidths=[16.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ACCENT_BG),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBEFORE', (0, 0), (0, -1), 4, LIGHT_BLUE),
    ]))
    return t


def build():
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.4*cm, bottomMargin=1.1*cm,
        title='Alltrucks AMCAT — Récapitulatif assistant hotline',
        author='Alltrucks AMCAT',
    )
    styles = build_styles()
    flow = []
    P = lambda t, s='Body2': Paragraph(t, styles[s])

    # ── PAGE 1 : COUVERTURE (header dessiné dans cover_chrome, intro en flow) ──
    # Pousse le flow dans la zone blanche, sous le bloc coloré qui couvre ~64 %
    # du haut de la page (dark blue + bande light-blue).
    flow.append(Spacer(1, PAGE_HEIGHT * 0.62))
    flow.append(Paragraph("Objectif et valeur métier", styles['SubTitle']))
    flow.append(P(
        "L'assistant AMCAT répond automatiquement aux mails reçus par la hotline Alltrucks. "
        "Quand un atelier envoie une demande (via le portail ou le forum), le système identifie "
        "le véhicule et le problème, détecte la langue du message, cherche dans l'historique de "
        "la hotline les cas similaires déjà résolus, rédige une réponse de diagnostic structurée "
        "dans la langue de l'atelier, et envoie le mail. Objectif&nbsp;: fournir une première "
        "réponse de qualité en quelques secondes pendant qu'un opérateur humain reste prévenu "
        "pour la suite."
    ))
    flow.append(PageBreak())

    # ── PAGE 2 : Réception + Base de connaissances ───────────────────────
    flow.append(Paragraph("1. Réception et compréhension du mail entrant", styles['SubTitle']))
    flow.append(bullets([
        "Deux sources reconnues automatiquement&nbsp;: le <b>portail hotline</b> (formulaire structuré avec véhicule, problème, code défaut, nature de la demande) et le <b>forum technique</b> (post libre).",
        "<b>Détection automatique de la langue</b> du message&nbsp;: la réponse de l'IA est rédigée dans la langue de l'atelier, quelle qu'elle soit. Le contenu statique du mail (titres, libellés, disclaimer) est traduit en français, allemand, italien, espagnol et polonais&nbsp;; pour les autres langues, ces parties statiques restent en anglais.",
        "Si la demande est purement documentaire (le mécanicien a uniquement coché \"envoyer les données techniques / documentation\"), l'IA n'est PAS appelée — un opérateur humain reprendra la main.",
        "Chaque mail reçu est tracé avec un statut visible dans l'admin&nbsp;: reçu, arrêté, généré, envoyé, noté.",
    ], styles['Bullet2']))

    flow.append(Paragraph("2. Base de connaissances — capitalisation de l'historique hotline", styles['SubTitle']))
    flow.append(P(
        "Le système s'appuie sur l'historique réel de la hotline Alltrucks pour ancrer ses réponses "
        "dans des cas vécus. Le fichier d'export initial fourni contenait <b>~25 000 cas</b>. Après "
        "application des règles qualité ci-dessous, la base opérationnelle compte "
        "<b>6 863 cas</b> exploitables."
    ))
    flow.append(Paragraph("Règles de filtrage appliquées sur l'historique", styles['SubSubTitle']))
    flow.append(bullets([
        "<b>Exclusion des demandes purement documentaires</b> (\"Technische Dokumentation\")&nbsp;: leurs résolutions étaient majoritairement des phrases courtes du type \"document envoyé\" qui apportaient du bruit plutôt que de la connaissance utile.",
        "<b>Résolution suffisamment décrite</b> (≥ 100 caractères)&nbsp;: élimination des cas dont la réponse de l'opérateur était trop succincte (\"OK\", \"résolu\", quelques mots) pour être réutilisable.",
        "<b>Suppression des cas administratifs</b> (\"erledigt\", \"nicht zuständig\", \"résolu\"…) qui ne contiennent aucune information technique.",
        "<b>Normalisation des constructeurs</b> (Mercedes / MERCEDES-BENZ / mercedes &rarr; Mercedes-Benz, idem Iveco, MAN, Renault…) pour homogénéiser les recherches et éviter de scinder un même constructeur en plusieurs entrées.",
        "<b>Stockage à raison d'un cas par entrée</b> dans la mémoire de l'IA pour éviter qu'un cas mal rangé dans le fichier ne soit cité de manière disproportionnée par rapport à sa pertinence réelle.",
    ], styles['Bullet2']))

    flow.append(Paragraph("3. Rédaction de la réponse de diagnostic", styles['SubTitle']))
    flow.append(P("La réponse est générée selon des règles strictes, traduites au modèle d'IA via un prompt système versionné&nbsp;:"))
    flow.append(bullets([
        "<b>Langue de réponse</b>&nbsp;: exactement celle dans laquelle le mécanicien a écrit (la marque du véhicule n'a aucune influence — un Mercedes en anglais reçoit une réponse en anglais).",
        "<b>Outil de diagnostic unique cité</b>&nbsp;: <b>Bosch KTS Alltrucks</b>. Toute mention d'un outil OEM (MAN-Diagnose, Mercedes Xentry, DAF Davie, Volvo Tech Tool…) est interdite.",
        "<b>Pas de renvoi vers un tiers externe</b>&nbsp;: l'atelier qui reçoit le mail EST l'atelier qualifié. Pas de \"contactez le concessionnaire\", \"adressez-vous à un service partner\", \"consultez un technicien qualifié\" ou équivalent.",
        "<b>Phrase \"En se basant sur des cas similaires…\"</b>&nbsp;: utilisée uniquement quand la réponse s'appuie réellement sur l'historique. Sinon, le modèle s'exprime en son propre nom.",
        "<b>Structure imposée</b>&nbsp;: paragraphe d'introduction (interprétation du problème + causes typiques), phrase de transition, puis liste numérotée d'actions concrètes (titre en gras + 1–2 phrases d'explication).",
        "<b>Avertissements de sécurité</b>&nbsp;: toute étape risquée (haute pression, électrique, charge suspendue, AdBlue/carburant…) est préfixée par \"WARNING:\" traduit dans la langue de réponse.",
    ], styles['Bullet2']))

    flow.append(PageBreak())

    # ── PAGE 3 : Localisation + Pilotage + Améliorations ─────────────
    flow.append(Paragraph("4. Localisation du mail envoyé", styles['SubTitle']))
    flow.append(bullets([
        "Le contenu fixe du mail (titres de section, libellés des champs véhicule, intro, disclaimer IA, étiquettes de feedback) est traduit automatiquement selon la langue détectée.",
        "Les traductions FR · DE · IT · ES · PL sont éditables directement depuis Strapi — un changement de wording se fait sans déploiement technique.",
        "L'anglais sert de version de secours&nbsp;: si Strapi est indisponible ou si une traduction manque, le mail part quand même avec la version anglaise.",
        "Disclaimer IA visible en bas de chaque réponse&nbsp;: rappelle au lecteur que le contenu est généré par IA et doit être vérifié avant utilisation opérationnelle.",
    ], styles['Bullet2']))

    flow.append(Paragraph("5. Pilotage du système au quotidien", styles['SubTitle']))
    flow.append(bullets([
        "<b>Journal des mails entrants</b>&nbsp;: liste filtrable par date, statut, langue détectée. Permet de surveiller le flux et d'identifier rapidement les anomalies.",
        "<b>Page de détail d'un mail</b>&nbsp;: visualise les 4 étapes (réception, parsing, réponse IA, envoi). Affiche la réponse générée, les cas historiques cités (dépliables), la note utilisateur. Bouton \"Régénérer\" pour relancer une réponse si besoin.",
        "<b>Gestion de la base de connaissances</b>&nbsp;: ajout, modification ou suppression d'un cas via un formulaire dédié. La synchronisation avec l'IA est automatique.",
        "<b>Configuration de l'auto-répondeur</b>&nbsp;: activation/désactivation de l'IA et de l'envoi de mail, édition du prompt système, choix des destinataires de test.",
    ], styles['Bullet2']))

    flow.append(Paragraph("6. Améliorations possibles", styles['SubTitle']))
    flow.append(bullets([
        "<b>Élargir la base de connaissances</b>&nbsp;: ajouter de nouveaux cas réels au fil de l'eau (depuis l'admin) — c'est la principale source d'amélioration de la pertinence.",
        "<b>Support de langues supplémentaires</b>&nbsp;: norvégien, néerlandais, etc. Il suffit d'ajouter le code à <i>SUPPORTED_LANGUAGES</i> et de créer la locale Strapi correspondante.",
    ], styles['Bullet2']))

    flow.append(Spacer(1, 6))
    flow.append(callout(
        "L'efficacité du système croît avec la qualité et la quantité de la base de connaissances. "
        "Chaque cas ajouté ou affiné depuis l'admin enrichit immédiatement les réponses futures.",
        styles,
    ))

    flow.append(Spacer(1, 6))
    flow.append(Paragraph(
        "Document généré automatiquement à partir du code source.",
        styles['Caption2'],
    ))

    doc.build(flow, onFirstPage=cover_chrome, onLaterPages=page_chrome)
    print(f'PDF written to {OUTPUT}')


if __name__ == '__main__':
    build()