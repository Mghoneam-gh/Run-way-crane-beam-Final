"""
RUNWAY BEAM DESIGN TOOL V3.0
Per AISC 360-16 (ASD), AISC Design Guide 7, and CMAA 70
"""

import streamlit as st
import math
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dataclasses import dataclass, field
from typing import List, Dict
import io
from datetime import datetime

# PDF Generation imports
try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.units import mm, inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
                                     PageBreak, Image, KeepTogether, HRFlowable)
    from reportlab.lib.colors import HexColor
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

st.set_page_config(page_title="Runway Beam Design V3", page_icon="🏗️", layout="wide")

E_STEEL = 200000
G_STEEL = 77200
GRAVITY = 9.81

STEEL_GRADES = {
    'A36': {'Fy': 250, 'Fu': 400},
    'A572_Gr42': {'Fy': 290, 'Fu': 415},
    'A572_Gr50': {'Fy': 345, 'Fu': 450},
    'S235': {'Fy': 235, 'Fu': 360},
    'S275': {'Fy': 275, 'Fu': 430},
    'S355': {'Fy': 355, 'Fu': 510},
}

CRANE_CLASSES = {
    'A': {'name': 'Standby', 'cycles': '20K-100K', 'max_cycles': 100000, 'defl_limit': 600,
          'desc': 'Infrequent use, precise handling (powerhouses, transformer stations)'},
    'B': {'name': 'Light', 'cycles': '100K-500K', 'max_cycles': 500000, 'defl_limit': 600,
          'desc': 'Light service, repair shops, light assembly, service maintenance'},
    'C': {'name': 'Moderate', 'cycles': '500K-2M', 'max_cycles': 2000000, 'defl_limit': 600,
          'desc': 'Moderate service, machine shops, paper mills, light warehousing'},
    'D': {'name': 'Heavy', 'cycles': '2M-10M', 'max_cycles': 10000000, 'defl_limit': 800,
          'desc': 'Heavy service, heavy machine/fabrication shops, steel warehouses'},
    'E': {'name': 'Severe', 'cycles': '10M-20M', 'max_cycles': 20000000, 'defl_limit': 1000,
          'desc': 'Severe service, scrap yards, fertilizer plants, container handling'},
    'F': {'name': 'Continuous', 'cycles': '>20M', 'max_cycles': 50000000, 'defl_limit': 1000,
          'desc': 'Continuous severe service, steel mills, foundries, lumber mills'},
}

FATIGUE_CATS = {
    'A': {'Cf': 250e8, 'thresh': 165, 'desc': 'Base metal with rolled surfaces',
          'detail': 'Plain base metal, flame-cut edges with ANSI smoothness ≤1000'},
    'B': {'Cf': 120e8, 'thresh': 110, 'desc': 'Base metal at welded connections',
          'detail': 'Built-up members with continuous fillet welds, groove welds'},
    'C': {'Cf': 44e8, 'thresh': 69, 'desc': 'Welded stiffeners & attachments <2"',
          'detail': 'Transverse stiffener welds, short attachments <50mm'},
    'D': {'Cf': 22e8, 'thresh': 48, 'desc': 'Welded attachments 2"-4" long',
          'detail': 'Longitudinal attachments 50-100mm, cruciform joints'},
    'E': {'Cf': 11e8, 'thresh': 31, 'desc': 'Welded attachments >4", cover plates',
          'detail': 'Long attachments >100mm, partial length cover plates'},
    'F': {'Cf': 150e8, 'thresh': 55, 'desc': 'Shear stress on weld throat',
          'detail': 'Fillet welds loaded in shear, plug/slot welds'},
}

# ============================================================================
# COMPLETE STEEL SECTION DATABASE - All Standard Sections
# ============================================================================

# IPE Sections (European I-beams) - Complete Range
IPE = {
    'IPE 80':   {'d': 80,  'bf': 46,  'tf': 5.2,  'tw': 3.8, 'A': 764,   'Ix': 0.801e6, 'Iy': 0.0849e6, 'Sx': 20.0e3,  'mass': 6.0},
    'IPE 100':  {'d': 100, 'bf': 55,  'tf': 5.7,  'tw': 4.1, 'A': 1032,  'Ix': 1.71e6,  'Iy': 0.159e6,  'Sx': 34.2e3,  'mass': 8.1},
    'IPE 120':  {'d': 120, 'bf': 64,  'tf': 6.3,  'tw': 4.4, 'A': 1321,  'Ix': 3.18e6,  'Iy': 0.277e6,  'Sx': 53.0e3,  'mass': 10.4},
    'IPE 140':  {'d': 140, 'bf': 73,  'tf': 6.9,  'tw': 4.7, 'A': 1643,  'Ix': 5.41e6,  'Iy': 0.449e6,  'Sx': 77.3e3,  'mass': 12.9},
    'IPE 160':  {'d': 160, 'bf': 82,  'tf': 7.4,  'tw': 5.0, 'A': 2009,  'Ix': 8.69e6,  'Iy': 0.683e6,  'Sx': 109e3,   'mass': 15.8},
    'IPE 180':  {'d': 180, 'bf': 91,  'tf': 8.0,  'tw': 5.3, 'A': 2395,  'Ix': 13.2e6,  'Iy': 1.01e6,   'Sx': 146e3,   'mass': 18.8},
    'IPE 200':  {'d': 200, 'bf': 100, 'tf': 8.5,  'tw': 5.6, 'A': 2848,  'Ix': 19.4e6,  'Iy': 1.42e6,   'Sx': 194e3,   'mass': 22.4},
    'IPE 220':  {'d': 220, 'bf': 110, 'tf': 9.2,  'tw': 5.9, 'A': 3337,  'Ix': 27.7e6,  'Iy': 2.05e6,   'Sx': 252e3,   'mass': 26.2},
    'IPE 240':  {'d': 240, 'bf': 120, 'tf': 9.8,  'tw': 6.2, 'A': 3912,  'Ix': 38.9e6,  'Iy': 2.84e6,   'Sx': 324e3,   'mass': 30.7},
    'IPE 270':  {'d': 270, 'bf': 135, 'tf': 10.2, 'tw': 6.6, 'A': 4594,  'Ix': 57.9e6,  'Iy': 4.20e6,   'Sx': 429e3,   'mass': 36.1},
    'IPE 300':  {'d': 300, 'bf': 150, 'tf': 10.7, 'tw': 7.1, 'A': 5381,  'Ix': 83.6e6,  'Iy': 6.04e6,   'Sx': 557e3,   'mass': 42.2},
    'IPE 330':  {'d': 330, 'bf': 160, 'tf': 11.5, 'tw': 7.5, 'A': 6261,  'Ix': 118e6,   'Iy': 7.88e6,   'Sx': 713e3,   'mass': 49.1},
    'IPE 360':  {'d': 360, 'bf': 170, 'tf': 12.7, 'tw': 8.0, 'A': 7273,  'Ix': 163e6,   'Iy': 10.4e6,   'Sx': 904e3,   'mass': 57.1},
    'IPE 400':  {'d': 400, 'bf': 180, 'tf': 13.5, 'tw': 8.6, 'A': 8446,  'Ix': 231e6,   'Iy': 13.2e6,   'Sx': 1160e3,  'mass': 66.3},
    'IPE 450':  {'d': 450, 'bf': 190, 'tf': 14.6, 'tw': 9.4, 'A': 9882,  'Ix': 337e6,   'Iy': 16.8e6,   'Sx': 1500e3,  'mass': 77.6},
    'IPE 500':  {'d': 500, 'bf': 200, 'tf': 16.0, 'tw': 10.2,'A': 11550, 'Ix': 482e6,   'Iy': 21.4e6,   'Sx': 1930e3,  'mass': 90.7},
    'IPE 550':  {'d': 550, 'bf': 210, 'tf': 17.2, 'tw': 11.1,'A': 13440, 'Ix': 671e6,   'Iy': 26.7e6,   'Sx': 2440e3,  'mass': 106},
    'IPE 600':  {'d': 600, 'bf': 220, 'tf': 19.0, 'tw': 12.0,'A': 15600, 'Ix': 921e6,   'Iy': 33.9e6,   'Sx': 3070e3,  'mass': 122},
    'IPE 750x137': {'d': 753, 'bf': 263, 'tf': 17.0, 'tw': 11.5, 'A': 17440, 'Ix': 1603e6, 'Iy': 51.5e6, 'Sx': 4260e3, 'mass': 137},
    'IPE 750x147': {'d': 753, 'bf': 265, 'tf': 18.5, 'tw': 12.0, 'A': 18730, 'Ix': 1743e6, 'Iy': 57.2e6, 'Sx': 4630e3, 'mass': 147},
    'IPE 750x173': {'d': 762, 'bf': 267, 'tf': 21.6, 'tw': 14.4, 'A': 22040, 'Ix': 2050e6, 'Iy': 68.2e6, 'Sx': 5380e3, 'mass': 173},
    'IPE 750x196': {'d': 770, 'bf': 268, 'tf': 25.4, 'tw': 15.6, 'A': 24990, 'Ix': 2400e6, 'Iy': 81.4e6, 'Sx': 6240e3, 'mass': 196},
}

# HEA Sections (European Wide Flange - Light) - Complete Range
HEA = {
    'HEA 100':  {'d': 96,  'bf': 100, 'tf': 8.0,  'tw': 5.0, 'A': 2124,  'Ix': 3.49e6,  'Iy': 1.34e6,  'Sx': 72.8e3,  'mass': 16.7},
    'HEA 120':  {'d': 114, 'bf': 120, 'tf': 8.0,  'tw': 5.0, 'A': 2534,  'Ix': 6.06e6,  'Iy': 2.31e6,  'Sx': 106e3,   'mass': 19.9},
    'HEA 140':  {'d': 133, 'bf': 140, 'tf': 8.5,  'tw': 5.5, 'A': 3142,  'Ix': 10.3e6,  'Iy': 3.89e6,  'Sx': 155e3,   'mass': 24.7},
    'HEA 160':  {'d': 152, 'bf': 160, 'tf': 9.0,  'tw': 6.0, 'A': 3877,  'Ix': 16.7e6,  'Iy': 6.16e6,  'Sx': 220e3,   'mass': 30.4},
    'HEA 180':  {'d': 171, 'bf': 180, 'tf': 9.5,  'tw': 6.0, 'A': 4525,  'Ix': 25.1e6,  'Iy': 9.25e6,  'Sx': 294e3,   'mass': 35.5},
    'HEA 200':  {'d': 190, 'bf': 200, 'tf': 10.0, 'tw': 6.5, 'A': 5383,  'Ix': 36.9e6,  'Iy': 13.4e6,  'Sx': 389e3,   'mass': 42.3},
    'HEA 220':  {'d': 210, 'bf': 220, 'tf': 11.0, 'tw': 7.0, 'A': 6434,  'Ix': 54.1e6,  'Iy': 19.5e6,  'Sx': 515e3,   'mass': 50.5},
    'HEA 240':  {'d': 230, 'bf': 240, 'tf': 12.0, 'tw': 7.5, 'A': 7684,  'Ix': 77.6e6,  'Iy': 27.7e6,  'Sx': 675e3,   'mass': 60.3},
    'HEA 260':  {'d': 250, 'bf': 260, 'tf': 12.5, 'tw': 7.5, 'A': 8682,  'Ix': 104e6,   'Iy': 36.7e6,  'Sx': 836e3,   'mass': 68.2},
    'HEA 280':  {'d': 270, 'bf': 280, 'tf': 13.0, 'tw': 8.0, 'A': 9726,  'Ix': 137e6,   'Iy': 47.5e6,  'Sx': 1010e3,  'mass': 76.4},
    'HEA 300':  {'d': 290, 'bf': 300, 'tf': 14.0, 'tw': 8.5, 'A': 11250, 'Ix': 183e6,   'Iy': 63.1e6,  'Sx': 1260e3,  'mass': 88.3},
    'HEA 320':  {'d': 310, 'bf': 300, 'tf': 15.5, 'tw': 9.0, 'A': 12440, 'Ix': 229e6,   'Iy': 69.8e6,  'Sx': 1480e3,  'mass': 97.6},
    'HEA 340':  {'d': 330, 'bf': 300, 'tf': 16.5, 'tw': 9.5, 'A': 13330, 'Ix': 276e6,   'Iy': 74.1e6,  'Sx': 1680e3,  'mass': 105},
    'HEA 360':  {'d': 350, 'bf': 300, 'tf': 17.5, 'tw': 10.0,'A': 14280, 'Ix': 331e6,   'Iy': 78.5e6,  'Sx': 1890e3,  'mass': 112},
    'HEA 400':  {'d': 390, 'bf': 300, 'tf': 19.0, 'tw': 11.0,'A': 15900, 'Ix': 451e6,   'Iy': 85.6e6,  'Sx': 2310e3,  'mass': 125},
    'HEA 450':  {'d': 440, 'bf': 300, 'tf': 21.0, 'tw': 11.5,'A': 17800, 'Ix': 637e6,   'Iy': 94.6e6,  'Sx': 2900e3,  'mass': 140},
    'HEA 500':  {'d': 490, 'bf': 300, 'tf': 23.0, 'tw': 12.0,'A': 19800, 'Ix': 869e6,   'Iy': 104e6,   'Sx': 3550e3,  'mass': 155},
    'HEA 550':  {'d': 540, 'bf': 300, 'tf': 24.0, 'tw': 12.5,'A': 21180, 'Ix': 1120e6,  'Iy': 111e6,   'Sx': 4150e3,  'mass': 166},
    'HEA 600':  {'d': 590, 'bf': 300, 'tf': 25.0, 'tw': 13.0,'A': 22640, 'Ix': 1410e6,  'Iy': 117e6,   'Sx': 4790e3,  'mass': 178},
    'HEA 650':  {'d': 640, 'bf': 300, 'tf': 26.0, 'tw': 13.5,'A': 24160, 'Ix': 1750e6,  'Iy': 124e6,   'Sx': 5470e3,  'mass': 190},
    'HEA 700':  {'d': 690, 'bf': 300, 'tf': 27.0, 'tw': 14.5,'A': 26050, 'Ix': 2150e6,  'Iy': 131e6,   'Sx': 6240e3,  'mass': 204},
    'HEA 800':  {'d': 790, 'bf': 300, 'tf': 28.0, 'tw': 15.0,'A': 28570, 'Ix': 3030e6,  'Iy': 137e6,   'Sx': 7680e3,  'mass': 224},
    'HEA 900':  {'d': 890, 'bf': 300, 'tf': 30.0, 'tw': 16.0,'A': 32120, 'Ix': 4220e6,  'Iy': 146e6,   'Sx': 9480e3,  'mass': 252},
    'HEA 1000': {'d': 990, 'bf': 300, 'tf': 31.0, 'tw': 16.5,'A': 34680, 'Ix': 5530e6,  'Iy': 152e6,   'Sx': 11180e3, 'mass': 272},
}

# HEB Sections (European Wide Flange - Medium) - Complete Range
HEB = {
    'HEB 100':  {'d': 100, 'bf': 100, 'tf': 10.0, 'tw': 6.0, 'A': 2604,  'Ix': 4.50e6,  'Iy': 1.67e6,  'Sx': 89.9e3,  'mass': 20.4},
    'HEB 120':  {'d': 120, 'bf': 120, 'tf': 11.0, 'tw': 6.5, 'A': 3401,  'Ix': 8.64e6,  'Iy': 3.18e6,  'Sx': 144e3,   'mass': 26.7},
    'HEB 140':  {'d': 140, 'bf': 140, 'tf': 12.0, 'tw': 7.0, 'A': 4296,  'Ix': 15.1e6,  'Iy': 5.50e6,  'Sx': 216e3,   'mass': 33.7},
    'HEB 160':  {'d': 160, 'bf': 160, 'tf': 13.0, 'tw': 8.0, 'A': 5425,  'Ix': 24.9e6,  'Iy': 8.89e6,  'Sx': 311e3,   'mass': 42.6},
    'HEB 180':  {'d': 180, 'bf': 180, 'tf': 14.0, 'tw': 8.5, 'A': 6525,  'Ix': 38.3e6,  'Iy': 13.6e6,  'Sx': 426e3,   'mass': 51.2},
    'HEB 200':  {'d': 200, 'bf': 200, 'tf': 15.0, 'tw': 9.0, 'A': 7808,  'Ix': 57.0e6,  'Iy': 20.0e6,  'Sx': 570e3,   'mass': 61.3},
    'HEB 220':  {'d': 220, 'bf': 220, 'tf': 16.0, 'tw': 9.5, 'A': 9104,  'Ix': 80.9e6,  'Iy': 28.4e6,  'Sx': 736e3,   'mass': 71.5},
    'HEB 240':  {'d': 240, 'bf': 240, 'tf': 17.0, 'tw': 10.0,'A': 10600, 'Ix': 112e6,   'Iy': 39.2e6,  'Sx': 938e3,   'mass': 83.2},
    'HEB 260':  {'d': 260, 'bf': 260, 'tf': 17.5, 'tw': 10.0,'A': 11840, 'Ix': 149e6,   'Iy': 51.3e6,  'Sx': 1150e3,  'mass': 93.0},
    'HEB 280':  {'d': 280, 'bf': 280, 'tf': 18.0, 'tw': 10.5,'A': 13140, 'Ix': 193e6,   'Iy': 65.9e6,  'Sx': 1380e3,  'mass': 103},
    'HEB 300':  {'d': 300, 'bf': 300, 'tf': 19.0, 'tw': 11.0,'A': 14910, 'Ix': 252e6,   'Iy': 85.6e6,  'Sx': 1680e3,  'mass': 117},
    'HEB 320':  {'d': 320, 'bf': 300, 'tf': 20.5, 'tw': 11.5,'A': 16130, 'Ix': 308e6,   'Iy': 93.9e6,  'Sx': 1930e3,  'mass': 127},
    'HEB 340':  {'d': 340, 'bf': 300, 'tf': 21.5, 'tw': 12.0,'A': 17090, 'Ix': 366e6,   'Iy': 96.9e6,  'Sx': 2160e3,  'mass': 134},
    'HEB 360':  {'d': 360, 'bf': 300, 'tf': 22.5, 'tw': 12.5,'A': 18060, 'Ix': 432e6,   'Iy': 101e6,   'Sx': 2400e3,  'mass': 142},
    'HEB 400':  {'d': 400, 'bf': 300, 'tf': 24.0, 'tw': 13.5,'A': 19780, 'Ix': 577e6,   'Iy': 108e6,   'Sx': 2880e3,  'mass': 155},
    'HEB 450':  {'d': 450, 'bf': 300, 'tf': 26.0, 'tw': 14.0,'A': 21830, 'Ix': 799e6,   'Iy': 117e6,   'Sx': 3550e3,  'mass': 171},
    'HEB 500':  {'d': 500, 'bf': 300, 'tf': 28.0, 'tw': 14.5,'A': 23860, 'Ix': 1072e6,  'Iy': 126e6,   'Sx': 4290e3,  'mass': 187},
    'HEB 550':  {'d': 550, 'bf': 300, 'tf': 29.0, 'tw': 15.0,'A': 25440, 'Ix': 1367e6,  'Iy': 131e6,   'Sx': 4970e3,  'mass': 199},
    'HEB 600':  {'d': 600, 'bf': 300, 'tf': 30.0, 'tw': 15.5,'A': 27000, 'Ix': 1710e6,  'Iy': 135e6,   'Sx': 5700e3,  'mass': 212},
    'HEB 650':  {'d': 650, 'bf': 300, 'tf': 31.0, 'tw': 16.0,'A': 28630, 'Ix': 2110e6,  'Iy': 140e6,   'Sx': 6480e3,  'mass': 225},
    'HEB 700':  {'d': 700, 'bf': 300, 'tf': 32.0, 'tw': 17.0,'A': 30640, 'Ix': 2569e6,  'Iy': 144e6,   'Sx': 7340e3,  'mass': 241},
    'HEB 800':  {'d': 800, 'bf': 300, 'tf': 33.0, 'tw': 17.5,'A': 33430, 'Ix': 3591e6,  'Iy': 149e6,   'Sx': 8980e3,  'mass': 262},
    'HEB 900':  {'d': 900, 'bf': 300, 'tf': 35.0, 'tw': 18.5,'A': 37110, 'Ix': 4941e6,  'Iy': 158e6,   'Sx': 10980e3, 'mass': 291},
    'HEB 1000': {'d': 1000,'bf': 300, 'tf': 36.0, 'tw': 19.0,'A': 40040, 'Ix': 6444e6,  'Iy': 163e6,   'Sx': 12890e3, 'mass': 314},
}

UB = {
    'UB 305x165x40': {'d': 303.4, 'bf': 165.0, 'tf': 10.2, 'tw': 6.0, 'A': 5125, 'Ix': 85.5e6, 'Iy': 7.64e6, 'Sx': 564e3, 'mass': 40.3},
    'UB 356x171x51': {'d': 355.0, 'bf': 171.5, 'tf': 11.5, 'tw': 7.4, 'A': 6490, 'Ix': 142e6, 'Iy': 9.68e6, 'Sx': 800e3, 'mass': 51.0},
    'UB 406x178x60': {'d': 406.4, 'bf': 177.9, 'tf': 12.8, 'tw': 7.9, 'A': 7640, 'Ix': 215e6, 'Iy': 12.0e6, 'Sx': 1060e3, 'mass': 60.1},
    'UB 457x191x67': {'d': 453.4, 'bf': 189.9, 'tf': 12.7, 'tw': 8.5, 'A': 8550, 'Ix': 294e6, 'Iy': 14.5e6, 'Sx': 1300e3, 'mass': 67.1},
    'UB 457x191x82': {'d': 460.0, 'bf': 191.3, 'tf': 16.0, 'tw': 9.9, 'A': 10400, 'Ix': 370e6, 'Iy': 18.5e6, 'Sx': 1610e3, 'mass': 82.0},
    'UB 533x210x92': {'d': 533.1, 'bf': 209.3, 'tf': 15.6, 'tw': 10.1, 'A': 11700, 'Ix': 554e6, 'Iy': 23.9e6, 'Sx': 2080e3, 'mass': 92.1},
    'UB 610x229x101': {'d': 602.6, 'bf': 227.6, 'tf': 14.8, 'tw': 10.5, 'A': 12900, 'Ix': 756e6, 'Iy': 29.4e6, 'Sx': 2510e3, 'mass': 101},
}

UC = {
    'UC 203x203x46': {'d': 203.2, 'bf': 203.6, 'tf': 11.0, 'tw': 7.2, 'A': 5870, 'Ix': 45.7e6, 'Iy': 15.4e6, 'Sx': 450e3, 'mass': 46.1},
    'UC 203x203x60': {'d': 209.6, 'bf': 205.8, 'tf': 14.2, 'tw': 9.4, 'A': 7640, 'Ix': 61.2e6, 'Iy': 20.5e6, 'Sx': 584e3, 'mass': 60.0},
    'UC 254x254x73': {'d': 254.1, 'bf': 254.6, 'tf': 14.2, 'tw': 8.6, 'A': 9320, 'Ix': 114e6, 'Iy': 39.4e6, 'Sx': 898e3, 'mass': 73.1},
    'UC 254x254x89': {'d': 260.3, 'bf': 256.3, 'tf': 17.3, 'tw': 10.3, 'A': 11400, 'Ix': 143e6, 'Iy': 48.5e6, 'Sx': 1100e3, 'mass': 89.5},
    'UC 305x305x97': {'d': 307.9, 'bf': 305.3, 'tf': 15.4, 'tw': 9.9, 'A': 12300, 'Ix': 222e6, 'Iy': 72.9e6, 'Sx': 1440e3, 'mass': 96.9},
    'UC 305x305x118': {'d': 314.5, 'bf': 307.4, 'tf': 18.7, 'tw': 12.0, 'A': 15000, 'Ix': 276e6, 'Iy': 90.7e6, 'Sx': 1760e3, 'mass': 118},
}

UPN = {
    'UPN 100': {'d': 100, 'bf': 50, 'tf': 8.5, 'tw': 6.0, 'A': 1350, 'Iy': 0.293e6, 'mass': 10.6, 'cy': 15.5},
    'UPN 120': {'d': 120, 'bf': 55, 'tf': 9.0, 'tw': 7.0, 'A': 1700, 'Iy': 0.432e6, 'mass': 13.4, 'cy': 16.0},
    'UPN 140': {'d': 140, 'bf': 60, 'tf': 10.0, 'tw': 7.0, 'A': 2040, 'Iy': 0.627e6, 'mass': 16.0, 'cy': 17.5},
    'UPN 160': {'d': 160, 'bf': 65, 'tf': 10.5, 'tw': 7.5, 'A': 2400, 'Iy': 0.853e6, 'mass': 18.8, 'cy': 18.4},
    'UPN 180': {'d': 180, 'bf': 70, 'tf': 11.0, 'tw': 8.0, 'A': 2800, 'Iy': 1.14e6, 'mass': 22.0, 'cy': 19.2},
    'UPN 200': {'d': 200, 'bf': 75, 'tf': 11.5, 'tw': 8.5, 'A': 3220, 'Iy': 1.48e6, 'mass': 25.3, 'cy': 20.1},
    'UPN 220': {'d': 220, 'bf': 80, 'tf': 12.5, 'tw': 9.0, 'A': 3740, 'Iy': 1.97e6, 'mass': 29.4, 'cy': 21.2},
    'UPN 240': {'d': 240, 'bf': 85, 'tf': 13.0, 'tw': 9.5, 'A': 4230, 'Iy': 2.48e6, 'mass': 33.2, 'cy': 22.0},
    'UPN 260': {'d': 260, 'bf': 90, 'tf': 14.0, 'tw': 10.0, 'A': 4830, 'Iy': 3.17e6, 'mass': 37.9, 'cy': 23.6},
    'UPN 280': {'d': 280, 'bf': 95, 'tf': 15.0, 'tw': 10.0, 'A': 5330, 'Iy': 3.99e6, 'mass': 41.8, 'cy': 25.3},
    'UPN 300': {'d': 300, 'bf': 100, 'tf': 16.0, 'tw': 10.0, 'A': 5880, 'Iy': 4.95e6, 'mass': 46.2, 'cy': 27.0},
}

PFC = {
    'PFC 125': {'d': 125, 'bf': 65, 'tf': 9.5, 'tw': 5.5, 'A': 1680, 'Iy': 0.631e6, 'mass': 13.2, 'cy': 18.6},
    'PFC 150': {'d': 150, 'bf': 75, 'tf': 10.0, 'tw': 5.5, 'A': 2080, 'Iy': 1.06e6, 'mass': 16.3, 'cy': 21.3},
    'PFC 180': {'d': 180, 'bf': 90, 'tf': 12.5, 'tw': 6.5, 'A': 3220, 'Iy': 2.38e6, 'mass': 25.3, 'cy': 26.5},
    'PFC 200': {'d': 200, 'bf': 90, 'tf': 14.0, 'tw': 6.5, 'A': 3610, 'Iy': 2.69e6, 'mass': 28.4, 'cy': 26.1},
    'PFC 230': {'d': 230, 'bf': 90, 'tf': 14.0, 'tw': 7.5, 'A': 4210, 'Iy': 2.87e6, 'mass': 33.0, 'cy': 25.3},
    'PFC 260': {'d': 260, 'bf': 90, 'tf': 14.0, 'tw': 8.0, 'A': 4670, 'Iy': 2.97e6, 'mass': 36.6, 'cy': 24.6},
    'PFC 300': {'d': 300, 'bf': 100, 'tf': 16.5, 'tw': 9.0, 'A': 6100, 'Iy': 4.68e6, 'mass': 47.9, 'cy': 27.8},
}

SECTION_DB = {'IPE': IPE, 'HEA': HEA, 'HEB': HEB, 'UB': UB, 'UC': UC}
CHANNEL_DB = {'UPN': UPN, 'PFC': PFC}


@dataclass
class CraneData:
    crane_id: int = 1
    capacity_tonnes: float = 10.0
    bridge_weight: float = 5.0  # Weight of bridge without trolley (tonnes)
    trolley_weight: float = 0.72  # Weight of crab/trolley (tonnes)
    bridge_span: float = 15.0  # Bridge span (m)
    min_hook_approach: float = 1.0  # Minimum distance from hook to runway rail (m)
    wheel_base: float = 2.2  # Distance between wheels on same rail (m)
    buffer_left: float = 0.29  # Distance from left wheel to left buffer (m)
    buffer_right: float = 0.29  # Distance from right wheel to right buffer (m)
    num_wheels: int = 2  # Wheels per rail
    impact_v: float = 0.25
    impact_h: float = 0.20
    impact_l: float = 0.10
    
    # Direct input option (from manufacturer data)
    use_direct_input: bool = False
    direct_max_wheel_load: float = 0.0  # Static max wheel load from manufacturer (kN)
    direct_min_wheel_load: float = 0.0  # Static min wheel load from manufacturer (kN)
    direct_lateral_load: float = 0.0  # Lateral load per wheel from manufacturer (kN)
    
    # Calculated values
    R_max: float = 0.0
    R_min: float = 0.0
    max_wheel_load: float = 0.0
    min_wheel_load: float = 0.0
    
    def calc_wheel_loads(self):
        """
        Calculate max and min wheel loads.
        
        If use_direct_input=True, uses manufacturer-provided wheel loads.
        Otherwise, calculates from bridge geometry.
        """
        if self.use_direct_input and self.direct_max_wheel_load > 0:
            # Use manufacturer-provided wheel loads (already static, no impact)
            self.max_wheel_load = self.direct_max_wheel_load
            self.min_wheel_load = self.direct_min_wheel_load if self.direct_min_wheel_load > 0 else self.direct_max_wheel_load * 0.2
            self.R_max = self.max_wheel_load * self.num_wheels
            self.R_min = self.min_wheel_load * self.num_wheels
        else:
            # Calculate from bridge geometry
            Lb = self.bridge_span
            e_min = self.min_hook_approach
            
            # Loads in kN
            P_lift = self.capacity_tonnes * GRAVITY
            P_trolley = self.trolley_weight * GRAVITY
            P_bridge = self.bridge_weight * GRAVITY
            
            # Bridge self-weight distributed equally
            R_bridge_each = P_bridge / 2.0
            
            # Moving load
            P_moving = P_lift + P_trolley
            
            # Maximum reaction (trolley nearest)
            R_moving_max = P_moving * (Lb - e_min) / Lb
            self.R_max = R_bridge_each + R_moving_max
            
            # Minimum reaction (trolley farthest)
            R_moving_min = P_moving * e_min / Lb
            self.R_min = R_bridge_each + R_moving_min
            
            # Wheel loads
            self.max_wheel_load = self.R_max / self.num_wheels
            self.min_wheel_load = self.R_min / self.num_wheels
        
        return self.max_wheel_load, self.min_wheel_load
    
    def wheel_load_with_impact(self):
        """Maximum wheel load including vertical impact"""
        self.calc_wheel_loads()
        return self.max_wheel_load * (1 + self.impact_v)
    
    def min_wheel_load_with_impact(self):
        """Minimum wheel load including vertical impact"""
        self.calc_wheel_loads()
        return self.min_wheel_load * (1 + self.impact_v)
    
    def lateral_per_wheel(self):
        """Lateral load per wheel"""
        if self.use_direct_input and self.direct_lateral_load > 0:
            return self.direct_lateral_load
        else:
            P_lift = self.capacity_tonnes * GRAVITY
            P_trolley = self.trolley_weight * GRAVITY
            H_total = self.impact_h * (P_lift + P_trolley)
            return H_total / (2 * self.num_wheels)
    
    def longitudinal_force(self):
        """Longitudinal force"""
        self.calc_wheel_loads()
        return self.impact_l * self.R_max
    
    def get_load_summary(self):
        """Return a summary of all calculated loads"""
        self.calc_wheel_loads()
        return {
            'R_max': self.R_max,
            'R_min': self.R_min,
            'max_wheel_static': self.max_wheel_load,
            'min_wheel_static': self.min_wheel_load,
            'max_wheel_impact': self.wheel_load_with_impact(),
            'min_wheel_impact': self.min_wheel_load_with_impact(),
            'lateral_per_wheel': self.lateral_per_wheel(),
            'longitudinal': self.longitudinal_force(),
        }


@dataclass
class WheelPos:
    crane_id: int
    wheel_id: int
    pos: float
    Pv: float
    Ph: float


@dataclass
class LoadCase:
    desc: str
    wheels: List[WheelPos]
    M_max: float
    M_pos: float
    V_max: float
    V_pos: float
    R_left: float
    R_right: float
    positions: List[float] = field(default_factory=list)
    moments: List[float] = field(default_factory=list)
    shears: List[float] = field(default_factory=list)


@dataclass 
class Section:
    name: str = "Custom"
    sec_type: str = "built_up"
    d: float = 0
    bf_top: float = 0
    tf_top: float = 0
    bf_bot: float = 0
    tf_bot: float = 0
    tw: float = 0
    hw: float = 0
    has_cap: bool = False
    cap_name: str = ""
    cap_A: float = 0
    cap_Iy: float = 0
    cap_d: float = 0
    cap_cy: float = 0
    A: float = 0
    Ix: float = 0
    Iy: float = 0
    Sx: float = 0
    Sy: float = 0
    Zx: float = 0
    rx: float = 0
    ry: float = 0
    rts: float = 0
    J: float = 0
    Cw: float = 0
    ho: float = 0
    y_bar: float = 0
    mass: float = 0
    
    def calc_props(self):
        A_tf = self.bf_top * self.tf_top
        A_bf = self.bf_bot * self.tf_bot
        A_w = self.hw * self.tw
        A_I = A_tf + A_bf + A_w
        y_tf = self.tf_bot + self.hw + self.tf_top/2
        y_bf = self.tf_bot/2
        y_w = self.tf_bot + self.hw/2
        
        if self.has_cap and self.cap_A > 0:
            y_cap = self.d + self.cap_cy
            self.A = A_I + self.cap_A
            self.y_bar = (A_tf*y_tf + A_bf*y_bf + A_w*y_w + self.cap_A*y_cap) / self.A
        else:
            self.A = A_I
            self.y_bar = (A_tf*y_tf + A_bf*y_bf + A_w*y_w) / max(A_I, 1)
        
        self.ho = self.d - (self.tf_top + self.tf_bot)/2
        I_tf = self.bf_top*self.tf_top**3/12 + A_tf*(y_tf - self.y_bar)**2
        I_bf = self.bf_bot*self.tf_bot**3/12 + A_bf*(y_bf - self.y_bar)**2
        I_w = self.tw*self.hw**3/12 + A_w*(y_w - self.y_bar)**2
        
        if self.has_cap and self.cap_A > 0:
            y_cap = self.d + self.cap_cy
            I_cap = self.cap_Iy + self.cap_A*(y_cap - self.y_bar)**2
            self.Ix = I_tf + I_bf + I_w + I_cap
        else:
            self.Ix = I_tf + I_bf + I_w
        
        self.Iy = self.tf_top*self.bf_top**3/12 + self.tf_bot*self.bf_bot**3/12 + self.hw*self.tw**3/12
        c_top = (self.d + self.cap_d if self.has_cap else self.d) - self.y_bar
        self.Sx = self.Ix / max(c_top, 1)
        self.Sy = self.Iy / max(self.bf_top/2, self.bf_bot/2, 1)
        self.rx = math.sqrt(self.Ix / max(self.A, 1))
        self.ry = math.sqrt(self.Iy / max(self.A, 1))
        self.Zx = self.Sx * 1.12
        self.J = self.bf_top*self.tf_top**3/3 + self.bf_bot*self.tf_bot**3/3 + self.hw*self.tw**3/3
        self.Cw = self.Iy * self.ho**2 / 4 if self.ho > 0 else 1
        self.rts = math.sqrt(math.sqrt(self.Iy * self.Cw) / max(self.Sx, 1))
        self.mass = self.A * 7850 / 1e6
        if self.has_cap:
            self.mass += self.cap_A * 7850 / 1e6
        return self


def analyze_load(L, wheels):
    if not wheels:
        return None
    sum_P = sum(w.Pv for w in wheels)
    sum_M = sum(w.Pv * w.pos for w in wheels)
    R_r = sum_M / max(L, 0.1)
    R_l = sum_P - R_r
    pts = sorted(set([0] + [w.pos for w in wheels] + [L] + [i*L/100 for i in range(101)]))
    M_list, V_list = [], []
    for x in pts:
        M = R_l * x
        V = R_l
        for w in wheels:
            if w.pos < x:
                M -= w.Pv * (x - w.pos)
            if w.pos <= x:
                V -= w.Pv
        M_list.append(M)
        V_list.append(V)
    m_idx = max(range(len(M_list)), key=lambda i: abs(M_list[i]))
    v_idx = max(range(len(V_list)), key=lambda i: abs(V_list[i]))
    return LoadCase("", wheels, M_list[m_idx], pts[m_idx], abs(V_list[v_idx]), pts[v_idx], R_l, R_r, pts, M_list, V_list)


def find_critical(L, cranes):
    """
    Find critical load cases for runway beam.
    
    Worst case scenarios:
    - Max Moment: Position loads so resultant and critical wheel are equidistant from midspan
    - Max Shear: Heaviest wheel directly over support, other loads as close as possible
    - Max Reaction: Same as max shear (reaction = shear at support)
    """
    results = []
    
    # Sort cranes by wheel load (heaviest first) for shear cases
    cranes_by_load = sorted(cranes, key=lambda c: c.wheel_load_with_impact(), reverse=True)
    
    # ============================================
    # SINGLE CRANE CASES
    # ============================================
    for c in cranes:
        Pv = c.wheel_load_with_impact()
        Ph = c.lateral_per_wheel()
        crane_length = c.wheel_base * (c.num_wheels - 1)
        
        if crane_length > L:
            continue
            
        # --- Single Crane: Max Moment ---
        # For 2 wheels: max moment when midpoint of wheels is slightly offset from beam center
        # Position so that resultant and nearest wheel are equidistant from center
        best_M, best_case = 0, None
        for pos in np.linspace(0, L - crane_length, 60):
            wheels = [WheelPos(c.crane_id, w+1, pos + w*c.wheel_base, Pv, Ph) for w in range(c.num_wheels)]
            case = analyze_load(L, wheels)
            if case and abs(case.M_max) > best_M:
                best_M = abs(case.M_max)
                best_case = case
        if best_case:
            best_case.desc = f"Crane {c.crane_id} ({c.capacity_tonnes:.0f}T): Max M"
            results.append(best_case)
        
        # --- Single Crane: Max Shear (wheel at left support) ---
        wheels = [WheelPos(c.crane_id, w+1, 0.0 + w*c.wheel_base, Pv, Ph) for w in range(c.num_wheels)]
        case = analyze_load(L, wheels)
        if case:
            case.desc = f"Crane {c.crane_id} ({c.capacity_tonnes:.0f}T): Max V (left)"
            results.append(case)
        
        # --- Single Crane: Max Shear (wheel at right support) ---
        pos_right = L - crane_length
        wheels = [WheelPos(c.crane_id, w+1, pos_right + w*c.wheel_base, Pv, Ph) for w in range(c.num_wheels)]
        case = analyze_load(L, wheels)
        if case:
            case.desc = f"Crane {c.crane_id} ({c.capacity_tonnes:.0f}T): Max V (right)"
            results.append(case)
    
    # ============================================
    # TWO CRANE CASES
    # ============================================
    if len(cranes) >= 2:
        c1, c2 = cranes[0], cranes[1]
        # Minimum gap = buffer_right of crane 1 + buffer_left of crane 2
        gap = c1.buffer_right + c2.buffer_left
        
        Pv1, Ph1 = c1.wheel_load_with_impact(), c1.lateral_per_wheel()
        Pv2, Ph2 = c2.wheel_load_with_impact(), c2.lateral_per_wheel()
        
        c1_length = c1.wheel_base * (c1.num_wheels - 1)
        c2_length = c2.wheel_base * (c2.num_wheels - 1)
        total_needed = c1_length + gap + c2_length
        
        if total_needed <= L:
            # --- 2 Cranes: Max Moment ---
            # Search for position that gives maximum moment
            best_M, best_case = 0, None
            for p1 in np.linspace(0, L - total_needed, 30):
                p2 = p1 + c1_length + gap
                wheels = []
                for w in range(c1.num_wheels):
                    wheels.append(WheelPos(1, w+1, p1 + w*c1.wheel_base, Pv1, Ph1))
                for w in range(c2.num_wheels):
                    wheels.append(WheelPos(2, w+1, p2 + w*c2.wheel_base, Pv2, Ph2))
                case = analyze_load(L, wheels)
                if case and abs(case.M_max) > best_M:
                    best_M = abs(case.M_max)
                    best_case = case
            if best_case:
                best_case.desc = f"2 Cranes ({c1.capacity_tonnes:.0f}T+{c2.capacity_tonnes:.0f}T): Max M"
                results.append(best_case)
            
            # --- 2 Cranes: Max Shear - Crane 1 at left support ---
            wheels = []
            p1 = 0.0  # Crane 1 first wheel at support
            for w in range(c1.num_wheels):
                wheels.append(WheelPos(1, w+1, p1 + w*c1.wheel_base, Pv1, Ph1))
            p2 = p1 + c1_length + gap
            if p2 + c2_length <= L:
                for w in range(c2.num_wheels):
                    wheels.append(WheelPos(2, w+1, p2 + w*c2.wheel_base, Pv2, Ph2))
            case = analyze_load(L, wheels)
            if case:
                case.desc = f"2 Cranes: Max V (C1 at support)"
                results.append(case)
            
            # --- 2 Cranes: Max Shear - Crane 2 at left support ---
            # This might give higher shear if Crane 2 is heavier!
            wheels = []
            p2 = 0.0  # Crane 2 first wheel at support
            for w in range(c2.num_wheels):
                wheels.append(WheelPos(2, w+1, p2 + w*c2.wheel_base, Pv2, Ph2))
            p1 = p2 + c2_length + gap  # Crane 1 after Crane 2
            if p1 + c1_length <= L:
                for w in range(c1.num_wheels):
                    wheels.append(WheelPos(1, w+1, p1 + w*c1.wheel_base, Pv1, Ph1))
            case = analyze_load(L, wheels)
            if case:
                case.desc = f"2 Cranes: Max V (C2 at support)"
                results.append(case)
            
            # --- 2 Cranes: Max Reaction - Search for absolute maximum ---
            # Try all possible positions to find the maximum support reaction
            best_R, best_case = 0, None
            for p1 in np.linspace(0, max(0, L - total_needed), 40):
                p2 = p1 + c1_length + gap
                if p2 + c2_length > L:
                    continue
                wheels = []
                for w in range(c1.num_wheels):
                    wheels.append(WheelPos(1, w+1, p1 + w*c1.wheel_base, Pv1, Ph1))
                for w in range(c2.num_wheels):
                    wheels.append(WheelPos(2, w+1, p2 + w*c2.wheel_base, Pv2, Ph2))
                case = analyze_load(L, wheels)
                if case:
                    max_R = max(case.R_left, case.R_right)
                    if max_R > best_R:
                        best_R = max_R
                        best_case = case
            if best_case:
                best_case.desc = f"2 Cranes: Max Reaction"
                results.append(best_case)
            
            # --- 2 Cranes: Max Shear - Heaviest crane at support ---
            # Automatically put the heavier crane at support
            if Pv2 > Pv1:
                heavy, light = (c2, Pv2, Ph2, c2_length), (c1, Pv1, Ph1, c1_length)
            else:
                heavy, light = (c1, Pv1, Ph1, c1_length), (c2, Pv2, Ph2, c2_length)
            
            wheels = []
            p_heavy = 0.0
            for w in range(heavy[0].num_wheels):
                wheels.append(WheelPos(heavy[0].crane_id, w+1, p_heavy + w*heavy[0].wheel_base, heavy[1], heavy[2]))
            p_light = p_heavy + heavy[3] + gap
            if p_light + light[3] <= L:
                for w in range(light[0].num_wheels):
                    wheels.append(WheelPos(light[0].crane_id, w+1, p_light + w*light[0].wheel_base, light[1], light[2]))
            case = analyze_load(L, wheels)
            if case:
                case.desc = f"2 Cranes: Max V (heavy at support)"
                results.append(case)
    
    # ============================================
    # THREE CRANE CASES
    # ============================================
    if len(cranes) >= 3:
        c1, c2, c3 = cranes[0], cranes[1], cranes[2]
        # Minimum gaps between cranes
        gap12 = c1.buffer_right + c2.buffer_left
        gap23 = c2.buffer_right + c3.buffer_left
        
        Pv1, Ph1 = c1.wheel_load_with_impact(), c1.lateral_per_wheel()
        Pv2, Ph2 = c2.wheel_load_with_impact(), c2.lateral_per_wheel()
        Pv3, Ph3 = c3.wheel_load_with_impact(), c3.lateral_per_wheel()
        
        c1_len = c1.wheel_base * (c1.num_wheels - 1)
        c2_len = c2.wheel_base * (c2.num_wheels - 1)
        c3_len = c3.wheel_base * (c3.num_wheels - 1)
        
        total_min = c1_len + gap12 + c2_len + gap23 + c3_len
        
        if total_min <= L:
            # --- 3 Cranes: Max Moment ---
            best_M, best_case = 0, None
            for p1 in np.linspace(0, L - total_min, 20):
                p2 = p1 + c1_len + gap12
                p3 = p2 + c2_len + gap23
                wheels = []
                for w in range(c1.num_wheels):
                    wheels.append(WheelPos(1, w+1, p1 + w*c1.wheel_base, Pv1, Ph1))
                for w in range(c2.num_wheels):
                    wheels.append(WheelPos(2, w+1, p2 + w*c2.wheel_base, Pv2, Ph2))
                for w in range(c3.num_wheels):
                    wheels.append(WheelPos(3, w+1, p3 + w*c3.wheel_base, Pv3, Ph3))
                case = analyze_load(L, wheels)
                if case and abs(case.M_max) > best_M:
                    best_M = abs(case.M_max)
                    best_case = case
            if best_case:
                best_case.desc = f"3 Cranes: Max M"
                results.append(best_case)
            
            # --- 3 Cranes: Max Shear (heaviest at support) ---
            # Sort by wheel load and put heaviest at support
            crane_loads = [(c1, Pv1, Ph1, c1_len), (c2, Pv2, Ph2, c2_len), (c3, Pv3, Ph3, c3_len)]
            crane_loads.sort(key=lambda x: x[1], reverse=True)
            
            wheels = []
            pos = 0.0
            for i, (crane, Pv, Ph, clen) in enumerate(crane_loads):
                for w in range(crane.num_wheels):
                    wheel_pos = pos + w * crane.wheel_base
                    if wheel_pos <= L:
                        wheels.append(WheelPos(crane.crane_id, w+1, wheel_pos, Pv, Ph))
                if i < 2:
                    # Gap to next crane
                    next_crane = crane_loads[i+1][0]
                    pos += clen + crane.buffer_right + next_crane.buffer_left
            
            case = analyze_load(L, wheels)
            if case:
                case.desc = f"3 Cranes: Max V (heavy first)"
                results.append(case)
    
    return results


def get_governing(results):
    if not results:
        return {}
    return {
        'moment': max(results, key=lambda r: abs(r.M_max)),
        'shear': max(results, key=lambda r: r.V_max),
        'reaction': max(results, key=lambda r: max(r.R_left, r.R_right))
    }


def check_compact(sec, Fy):
    lf = sec.bf_top / max(2 * sec.tf_top, 1)
    lpf = 0.38 * math.sqrt(E_STEEL / Fy)
    lrf = 1.0 * math.sqrt(E_STEEL / Fy)
    flg = 'Compact' if lf <= lpf else ('Noncompact' if lf <= lrf else 'Slender')
    lw = sec.hw / max(sec.tw, 1)
    lpw = 3.76 * math.sqrt(E_STEEL / Fy)
    lrw = 5.70 * math.sqrt(E_STEEL / Fy)
    web = 'Compact' if lw <= lpw else ('Noncompact' if lw <= lrw else 'Slender')
    return {'flg': flg, 'web': web, 'lf': lf, 'lpf': lpf, 'lrf': lrf, 'lw': lw, 'lpw': lpw, 'lrw': lrw}


def calc_Lp_Lr(sec, Fy):
    Lp = 1.76 * sec.ry * math.sqrt(E_STEEL / Fy)
    if sec.Sx > 0 and sec.ho > 0 and sec.rts > 0:
        t1 = sec.J / (sec.Sx * sec.ho)
        t2 = math.sqrt(t1**2 + 6.76 * (0.7 * Fy / E_STEEL)**2)
        Lr = 1.95 * sec.rts * (E_STEEL / (0.7 * Fy)) * math.sqrt(t1 + t2)
    else:
        Lr = Lp * 3
    return Lp, Lr


def calc_plate_girder_Mn(sec, Fy, Lb, cmp):
    """
    Calculate Mn for plate girders per AISC 360-16 Chapter F4/F5.
    
    For built-up I-shaped members with slender webs:
    - F4: Doubly symmetric sections
    - F5: Singly symmetric sections with slender webs
    
    Key factors:
    - Rpg: Bending strength reduction factor for slender webs
    - aw: Ratio of web area to compression flange area
    """
    Mp = Fy * sec.Zx / 1e6  # Plastic moment (kN-m)
    My = Fy * sec.Sx / 1e6  # Yield moment (kN-m)
    
    # Web slenderness
    h_tw = sec.hw / max(sec.tw, 1)
    
    # Compression flange (assume top flange for positive moment)
    bf = sec.bf_top
    tf = sec.tf_top
    
    # Limiting width-thickness ratios for web
    lambda_pw = 3.76 * math.sqrt(E_STEEL / Fy)  # Compact
    lambda_rw = 5.70 * math.sqrt(E_STEEL / Fy)  # Noncompact limit
    
    # Check if web is slender
    web_is_slender = h_tw > lambda_rw
    
    if not web_is_slender:
        # Use standard Chapter F2/F3 provisions but return 6 values
        Mn, Lp, Lr, ltb = calc_Mn(sec, Fy, Lb, cmp)
        Rpg = 1.0  # No reduction for non-slender web
        Aw = sec.hw * sec.tw
        Afc = bf * tf
        aw = Aw / max(Afc, 1)
        return Mn, Lp, Lr, ltb, Rpg, aw
    
    # === PLATE GIRDER WITH SLENDER WEB (AISC F5) ===
    
    # aw = ratio of web area to compression flange area (F4-11)
    Aw = sec.hw * sec.tw
    Afc = bf * tf  # Compression flange area
    aw = Aw / max(Afc, 1)
    
    # Rpg = bending strength reduction factor (F5-6)
    # Rpg = 1 - aw/(1200 + 300*aw) * (hc/tw - 5.7*sqrt(E/Fy)) <= 1.0
    hc = sec.hw  # For doubly symmetric, hc = h/2 * 2 = h
    Rpg = 1 - aw / (1200 + 300 * aw) * (hc / sec.tw - 5.7 * math.sqrt(E_STEEL / Fy))
    Rpg = min(Rpg, 1.0)
    Rpg = max(Rpg, 0.5)  # Practical lower limit
    
    # Compression flange slenderness
    lambda_f = bf / (2 * tf)
    lambda_pf = 0.38 * math.sqrt(E_STEEL / Fy)  # Compact
    lambda_rf = 0.95 * math.sqrt(E_STEEL / (0.7 * Fy))  # Noncompact (for built-up)
    
    # Lateral-torsional buckling
    Lp, Lr = calc_Lp_Lr(sec, Fy)
    
    # Determine Mn based on limit states
    
    # 1. Compression Flange Yielding (F5-1)
    Mn_cfy = Rpg * Fy * sec.Sx / 1e6
    
    # 2. Lateral-Torsional Buckling (F5-2, F5-3, F5-4)
    if Lb <= Lp:
        Mn_ltb = Rpg * Fy * sec.Sx / 1e6
        ltb = "No LTB"
    elif Lb <= Lr:
        Cb = 1.0  # Conservative
        Mn_ltb = Cb * (Rpg * Fy * sec.Sx / 1e6 - (Rpg * Fy * sec.Sx / 1e6 - 0.7 * Rpg * Fy * sec.Sx / 1e6) * (Lb - Lp) / (Lr - Lp))
        Mn_ltb = min(Mn_ltb, Rpg * Fy * sec.Sx / 1e6)
        ltb = "Inelastic LTB"
    else:
        # Elastic LTB
        if sec.rts > 0 and sec.Sx > 0 and sec.ho > 0:
            Fcr = math.pi**2 * E_STEEL / (Lb / sec.rts)**2 * math.sqrt(1 + 0.078 * sec.J / (sec.Sx * sec.ho) * (Lb / sec.rts)**2)
        else:
            Fcr = 0.7 * Fy
        Mn_ltb = Rpg * Fcr * sec.Sx / 1e6
        ltb = "Elastic LTB"
    
    # 3. Compression Flange Local Buckling (F5-7, F5-8, F5-9)
    if lambda_f <= lambda_pf:
        # Compact flange
        Mn_flb = Rpg * Fy * sec.Sx / 1e6
    elif lambda_f <= lambda_rf:
        # Noncompact flange
        Mn_flb = Rpg * (Fy - 0.3 * Fy * (lambda_f - lambda_pf) / (lambda_rf - lambda_pf)) * sec.Sx / 1e6
    else:
        # Slender flange
        Fcr_flb = 0.9 * E_STEEL / lambda_f**2
        Mn_flb = Rpg * Fcr_flb * sec.Sx / 1e6
    
    # Governing Mn is minimum of all limit states
    Mn = min(Mn_cfy, Mn_ltb, Mn_flb)
    
    return Mn, Lp, Lr, ltb, Rpg, aw


def check_plate_girder_proportions(sec, Fy):
    """
    Check plate girder proportioning limits per AISC 360-16 F13.2
    Returns dict with all checks and status
    """
    checks = {}
    
    # F13.2(a) - Web slenderness limit without transverse stiffeners
    # h/tw <= 260 for unstiffened webs
    h_tw = sec.hw / sec.tw
    limit_unstiff = 260
    checks['web_slenderness_unstiff'] = {
        'check': 'Web Slenderness (Unstiffened)',
        'ref': 'AISC F13.2(a)',
        'formula': 'h/tw ≤ 260',
        'actual': h_tw,
        'limit': limit_unstiff,
        'status': 'OK' if h_tw <= limit_unstiff else 'NG',
        'note': 'For webs without transverse stiffeners'
    }
    
    # F13.2(b) - Maximum web slenderness with stiffeners
    # h/tw <= 11.7√(E/Fy) ≤ 270
    limit_stiff = min(11.7 * math.sqrt(E_STEEL / Fy), 270)
    checks['web_slenderness_stiff'] = {
        'check': 'Web Slenderness (With Stiffeners)',
        'ref': 'AISC F13.2(b)',
        'formula': 'h/tw ≤ 11.7√(E/Fy) ≤ 270',
        'actual': h_tw,
        'limit': limit_stiff,
        'status': 'OK' if h_tw <= limit_stiff else 'NG',
        'note': 'For webs with transverse stiffeners'
    }
    
    # F13.2(c) - Minimum flange thickness (for built-up sections)
    # bf/(2*tf) ≤ 1.0√(E/Fy) for unstiffened flanges
    bf_tf = sec.bf_top / (2 * sec.tf_top)
    flange_limit = 1.0 * math.sqrt(E_STEEL / Fy)
    checks['flange_slenderness'] = {
        'check': 'Flange Slenderness',
        'ref': 'AISC Table B4.1b Case 2',
        'formula': 'bf/(2tf) ≤ 1.0√(E/Fy)',
        'actual': bf_tf,
        'limit': flange_limit,
        'status': 'OK' if bf_tf <= flange_limit else 'NG'
    }
    
    # Additional proportion check: a/h for stiffener spacing
    # Generally a/h ≤ 3.0 for effective tension field action
    # (This will be checked in stiffener design)
    
    return checks


def calc_plate_girder_flexure_detailed(sec, Fy, Lb):
    """
    Comprehensive plate girder flexural strength calculation per AISC F4/F5
    Returns detailed results for all limit states
    """
    results = {}
    
    # === SECTION GEOMETRY ===
    # For singly symmetric sections, need to find ENA and PNA
    
    # Areas
    A_tf = sec.bf_top * sec.tf_top
    A_bf = sec.bf_bot * sec.tf_bot
    A_w = sec.hw * sec.tw
    A_total = A_tf + A_bf + A_w
    
    # Elastic Neutral Axis (ENA) - measured from bottom
    y_tf = sec.tf_bot + sec.hw + sec.tf_top / 2
    y_bf = sec.tf_bot / 2
    y_w = sec.tf_bot + sec.hw / 2
    
    y_ena = (A_tf * y_tf + A_bf * y_bf + A_w * y_w) / A_total
    
    # Plastic Neutral Axis (PNA) - where area above = area below
    # For doubly symmetric: PNA = ENA = d/2
    # For singly symmetric: need to solve
    if abs(sec.bf_top - sec.bf_bot) < 1 and abs(sec.tf_top - sec.tf_bot) < 1:
        # Doubly symmetric
        y_pna = sec.d / 2
        is_symmetric = True
    else:
        # Singly symmetric - find PNA iteratively
        is_symmetric = False
        # Simplified: assume PNA in web
        A_half = A_total / 2
        if A_bf >= A_half:
            # PNA in bottom flange
            y_pna = A_half / sec.bf_bot
        elif A_bf + A_w >= A_half:
            # PNA in web
            y_pna = sec.tf_bot + (A_half - A_bf) / sec.tw
        else:
            # PNA in top flange
            y_pna = sec.tf_bot + sec.hw + (A_half - A_bf - A_w) / sec.bf_top
    
    results['geometry'] = {
        'A_total': A_total,
        'y_ena': y_ena,
        'y_pna': y_pna,
        'is_symmetric': is_symmetric,
        'c_top': sec.d - y_ena,  # Distance to top fiber
        'c_bot': y_ena,  # Distance to bottom fiber
    }
    
    # === SECTION MODULI ===
    # Elastic section moduli
    I_x = sec.Ix
    S_xc = I_x / (sec.d - y_ena)  # To compression flange (top)
    S_xt = I_x / y_ena  # To tension flange (bottom)
    
    # Plastic section modulus (approximate for singly symmetric)
    # Zx = A_comp * y_c + A_tens * y_t
    if is_symmetric:
        Z_x = sec.Zx
    else:
        # More accurate calculation for singly symmetric
        A_above_pna = A_tf + (sec.hw - (y_pna - sec.tf_bot)) * sec.tw if y_pna > sec.tf_bot else A_tf + A_w + (sec.tf_bot - y_pna) * sec.bf_bot
        # Simplified: use approximate Zx
        Z_x = 1.12 * min(S_xc, S_xt)
    
    results['section_moduli'] = {
        'S_xc': S_xc,
        'S_xt': S_xt,
        'Z_x': Z_x,
        'My_c': Fy * S_xc / 1e6,  # Yield moment (compression)
        'My_t': Fy * S_xt / 1e6,  # Yield moment (tension)
        'Mp': Fy * Z_x / 1e6,  # Plastic moment
    }
    
    # === WEB PARAMETERS ===
    h_tw = sec.hw / sec.tw
    lambda_rw = 5.70 * math.sqrt(E_STEEL / Fy)
    web_is_slender = h_tw > lambda_rw
    
    # hc = twice the distance from centroid to inside of compression flange
    hc = 2 * (sec.d - y_ena - sec.tf_top)
    hc = max(hc, sec.hw)  # At least web height
    
    # Compression zone in web
    hp = 2 * (y_pna - sec.tf_bot) if y_pna > sec.tf_bot else 0
    
    # aw = web area / compression flange area
    Aw = sec.hw * sec.tw
    Afc = sec.bf_top * sec.tf_top
    aw = Aw / max(Afc, 1)
    aw = min(aw, 10)  # Limit per F4
    
    results['web'] = {
        'h_tw': h_tw,
        'lambda_rw': lambda_rw,
        'web_is_slender': web_is_slender,
        'hc': hc,
        'hp': hp,
        'aw': aw,
    }
    
    # === RPG - BENDING STRENGTH REDUCTION FACTOR ===
    if web_is_slender:
        Rpg = 1 - aw / (1200 + 300 * aw) * (hc / sec.tw - 5.7 * math.sqrt(E_STEEL / Fy))
        Rpg = min(max(Rpg, 0.5), 1.0)
    else:
        Rpg = 1.0
    
    results['Rpg'] = Rpg
    
    # === LIMIT STATE 1: COMPRESSION FLANGE YIELDING (F4.1/F5.1) ===
    Mn_cfy = Rpg * Fy * S_xc / 1e6
    results['compression_flange_yielding'] = {
        'Mn': Mn_cfy,
        'ref': 'AISC Eq. F5-1' if web_is_slender else 'AISC Eq. F4-1',
        'formula': 'Mn = Rpg × Fy × Sxc',
        'Rpg': Rpg,
        'Fy': Fy,
        'Sxc': S_xc,
    }
    
    # === LIMIT STATE 2: TENSION FLANGE YIELDING (F4.3/F5.3) ===
    # Only applies if Sxt < Sxc (singly symmetric with smaller tension flange)
    if S_xt < S_xc:
        Mn_tfy = Fy * S_xt / 1e6
        results['tension_flange_yielding'] = {
            'Mn': Mn_tfy,
            'ref': 'AISC Eq. F4-15/F5-10',
            'formula': 'Mn = Fy × Sxt',
            'Fy': Fy,
            'Sxt': S_xt,
            'applies': True,
        }
    else:
        Mn_tfy = float('inf')
        results['tension_flange_yielding'] = {
            'Mn': Mn_tfy,
            'applies': False,
            'note': 'Does not govern (Sxt ≥ Sxc)',
        }
    
    # === LIMIT STATE 3: LATERAL-TORSIONAL BUCKLING (F4.2/F5.2) ===
    Lp, Lr = calc_Lp_Lr(sec, Fy)
    
    if Lb <= Lp:
        Mn_ltb = Rpg * Fy * S_xc / 1e6
        ltb_case = "No LTB (Lb ≤ Lp)"
        Fcr_ltb = Fy
    elif Lb <= Lr:
        # Inelastic LTB
        Cb = 1.0  # Conservative
        Mn_ltb = Cb * (Rpg * Fy * S_xc / 1e6 - (Rpg * Fy * S_xc / 1e6 - 0.7 * Rpg * Fy * S_xc / 1e6) * (Lb - Lp) / (Lr - Lp))
        Mn_ltb = min(Mn_ltb, Rpg * Fy * S_xc / 1e6)
        ltb_case = "Inelastic LTB (Lp < Lb ≤ Lr)"
        Fcr_ltb = Mn_ltb * 1e6 / (Rpg * S_xc)
    else:
        # Elastic LTB
        if sec.rts > 0 and S_xc > 0 and sec.ho > 0:
            Fcr_ltb = math.pi**2 * E_STEEL / (Lb / sec.rts)**2 * math.sqrt(1 + 0.078 * sec.J / (S_xc * sec.ho) * (Lb / sec.rts)**2)
        else:
            Fcr_ltb = 0.7 * Fy
        Mn_ltb = Rpg * Fcr_ltb * S_xc / 1e6
        ltb_case = "Elastic LTB (Lb > Lr)"
    
    results['lateral_torsional_buckling'] = {
        'Mn': Mn_ltb,
        'ref': 'AISC F4.2/F5.2',
        'case': ltb_case,
        'Lp': Lp,
        'Lr': Lr,
        'Lb': Lb,
        'Fcr': Fcr_ltb,
        'Cb': 1.0,
    }
    
    # === LIMIT STATE 4: COMPRESSION FLANGE LOCAL BUCKLING (F4.2/F5.2) ===
    lambda_f = sec.bf_top / (2 * sec.tf_top)
    lambda_pf = 0.38 * math.sqrt(E_STEEL / Fy)
    kc = 4 / math.sqrt(h_tw)
    kc = max(min(kc, 0.76), 0.35)  # 0.35 ≤ kc ≤ 0.76
    lambda_rf = 0.95 * math.sqrt(kc * E_STEEL / (0.7 * Fy))
    
    if lambda_f <= lambda_pf:
        Mn_flb = Rpg * Fy * S_xc / 1e6
        flb_case = "Compact Flange (λf ≤ λpf)"
        Fcr_flb = Fy
    elif lambda_f <= lambda_rf:
        Fcr_flb = Fy - 0.3 * Fy * (lambda_f - lambda_pf) / (lambda_rf - lambda_pf)
        Mn_flb = Rpg * Fcr_flb * S_xc / 1e6
        flb_case = "Noncompact Flange (λpf < λf ≤ λrf)"
    else:
        Fcr_flb = 0.9 * E_STEEL * kc / lambda_f**2
        Mn_flb = Rpg * Fcr_flb * S_xc / 1e6
        flb_case = "Slender Flange (λf > λrf)"
    
    results['compression_flange_local_buckling'] = {
        'Mn': Mn_flb,
        'ref': 'AISC F4-12/F5-7,8,9',
        'case': flb_case,
        'lambda_f': lambda_f,
        'lambda_pf': lambda_pf,
        'lambda_rf': lambda_rf,
        'kc': kc,
        'Fcr': Fcr_flb,
    }
    
    # === GOVERNING MOMENT ===
    Mn_values = [
        ('Compression Flange Yielding', Mn_cfy),
        ('Tension Flange Yielding', Mn_tfy),
        ('Lateral-Torsional Buckling', Mn_ltb),
        ('Compression Flange Local Buckling', Mn_flb),
    ]
    
    governing = min(Mn_values, key=lambda x: x[1])
    results['governing'] = {
        'Mn': governing[1],
        'limit_state': governing[0],
        'all_values': Mn_values,
    }
    
    return results


def calc_plate_girder_shear_detailed(sec, Fy, stiff_spacing=None, end_panel=False):
    """
    Comprehensive plate girder shear strength calculation per AISC G2/G3
    
    Parameters:
    - stiff_spacing: Transverse stiffener spacing in mm (None = no stiffeners)
    - end_panel: True for end panels, False for interior panels
    
    Returns detailed results for shear strength
    """
    results = {}
    
    Aw = sec.hw * sec.tw  # Web area
    h_tw = sec.hw / sec.tw
    
    # === SHEAR BUCKLING COEFFICIENT kv ===
    if stiff_spacing is None or stiff_spacing <= 0:
        # No stiffeners
        kv = 5.34
        has_stiffeners = False
        a_h = float('inf')
    else:
        a_h = stiff_spacing / sec.hw
        has_stiffeners = True
        if a_h <= 3.0:
            kv = 5 + 5 / (a_h**2)
        else:
            kv = 5.34
    
    results['kv'] = {
        'value': kv,
        'a_h': a_h,
        'has_stiffeners': has_stiffeners,
        'ref': 'AISC Eq. G2-5',
    }
    
    # === WEB SHEAR COEFFICIENT Cv ===
    limit1 = 1.10 * math.sqrt(kv * E_STEEL / Fy)
    limit2 = 1.37 * math.sqrt(kv * E_STEEL / Fy)
    
    if h_tw <= limit1:
        Cv1 = 1.0
        cv_case = "Cv1 = 1.0 (h/tw ≤ 1.10√(kvE/Fy))"
    elif h_tw <= limit2:
        Cv1 = limit1 / h_tw
        cv_case = f"Cv1 = 1.10√(kvE/Fy) / (h/tw) (Eq. G2-3)"
    else:
        Cv1 = 1.51 * kv * E_STEEL / (h_tw**2 * Fy)
        cv_case = f"Cv1 = 1.51kvE / [(h/tw)²Fy] (Eq. G2-4)"
    
    results['Cv1'] = {
        'value': Cv1,
        'h_tw': h_tw,
        'limit1': limit1,
        'limit2': limit2,
        'case': cv_case,
    }
    
    # === NOMINAL SHEAR STRENGTH - WITHOUT TENSION FIELD ACTION ===
    Vn1 = 0.6 * Fy * Aw * Cv1 / 1000  # kN
    
    results['shear_no_tfa'] = {
        'Vn': Vn1,
        'ref': 'AISC Eq. G2-1',
        'formula': 'Vn = 0.6 × Fy × Aw × Cv1',
        'Aw': Aw,
        'Cv1': Cv1,
    }
    
    # === TENSION FIELD ACTION (G3) ===
    # TFA only applies if:
    # 1. Has transverse stiffeners
    # 2. a/h ≤ 3.0
    # 3. a/h ≤ [260/(h/tw)]²
    # 4. Not an end panel (or end panel with proper anchorage)
    
    tfa_applicable = False
    Vn2 = Vn1  # Default to no TFA
    
    if has_stiffeners and a_h <= 3.0:
        limit_ah = (260 / h_tw)**2
        if a_h <= limit_ah:
            if not end_panel:
                tfa_applicable = True
                
                # Cv2 for tension field action (Eq. G2-9)
                if h_tw <= limit1:
                    Cv2 = 1.0
                else:
                    Cv2 = limit1 / h_tw
                
                # Vn with TFA (Eq. G3-2)
                Vn2 = 0.6 * Fy * Aw * (Cv2 + (1 - Cv2) / (1.15 * math.sqrt(1 + a_h**2))) / 1000
                
                results['shear_tfa'] = {
                    'Vn': Vn2,
                    'ref': 'AISC Eq. G3-2',
                    'formula': 'Vn = 0.6FyAw[Cv2 + (1-Cv2)/(1.15√(1+(a/h)²))]',
                    'Cv2': Cv2,
                    'applicable': True,
                }
            else:
                results['shear_tfa'] = {
                    'applicable': False,
                    'reason': 'End panel - TFA not permitted without special anchorage',
                }
        else:
            results['shear_tfa'] = {
                'applicable': False,
                'reason': f'a/h = {a_h:.2f} > [260/(h/tw)]² = {limit_ah:.2f}',
            }
    else:
        results['shear_tfa'] = {
            'applicable': False,
            'reason': 'No stiffeners or a/h > 3.0',
        }
    
    # === GOVERNING SHEAR ===
    if tfa_applicable:
        Vn = Vn2
        governing = 'With Tension Field Action (G3)'
    else:
        Vn = Vn1
        governing = 'Without Tension Field Action (G2)'
    
    results['governing'] = {
        'Vn': Vn,
        'method': governing,
        'Omega_v': 1.67 if tfa_applicable else 1.50,
        'Va': Vn / (1.67 if tfa_applicable else 1.50),
    }
    
    return results


def check_minimum_weld_size(t_thin, t_thick):
    """
    Check minimum fillet weld size per AISC Table J2.4
    
    Parameters:
    - t_thin: Thickness of thinner part joined (mm)
    - t_thick: Thickness of thicker part joined (mm)
    
    Returns minimum weld size in mm
    """
    t_base = max(t_thin, t_thick)
    
    # Table J2.4 - Minimum Size of Fillet Welds
    # (converted to mm, original in inches)
    if t_base <= 6.35:  # ≤ 1/4"
        w_min = 3  # 1/8" = 3mm
    elif t_base <= 12.7:  # > 1/4" to 1/2"
        w_min = 5  # 3/16" = 5mm
    elif t_base <= 19.05:  # > 1/2" to 3/4"
        w_min = 6  # 1/4" = 6mm
    else:  # > 3/4"
        w_min = 8  # 5/16" = 8mm
    
    return w_min


def calc_weld_design(sec, Fy, Fu, V, weld_size, FEXX=482):
    """
    Check fillet weld design for plate girder web-to-flange connection
    
    Parameters:
    - V: Shear force (kN)
    - weld_size: Fillet weld leg size (mm)
    - FEXX: Electrode strength (MPa), default E70XX = 482 MPa
    
    Returns weld design results
    """
    results = {}
    
    # Minimum weld size check
    t_flange = max(sec.tf_top, sec.tf_bot)
    w_min = check_minimum_weld_size(sec.tw, t_flange)
    
    results['minimum_size'] = {
        'required': w_min,
        'provided': weld_size,
        'ref': 'AISC Table J2.4',
        'status': 'OK' if weld_size >= w_min else 'NG',
    }
    
    # Maximum weld size (J2.2b)
    w_max = sec.tw - 1.6  # For material ≥ 6mm thick
    results['maximum_size'] = {
        'limit': w_max,
        'provided': weld_size,
        'ref': 'AISC J2.2b',
        'status': 'OK' if weld_size <= w_max else 'NG',
    }
    
    # Weld throat
    a = 0.707 * weld_size  # Effective throat (mm)
    
    # Shear flow (horizontal shear per unit length)
    # q = V × Q / I
    # Q = First moment of flange about NA
    Q = sec.bf_top * sec.tf_top * (sec.d - sec.y_bar - sec.tf_top/2)
    q = V * 1000 * Q / sec.Ix  # N/mm
    
    # For two welds (both sides of web)
    q_per_weld = q / 2
    
    results['shear_flow'] = {
        'Q': Q,
        'I': sec.Ix,
        'V': V,
        'q_total': q,
        'q_per_weld': q_per_weld,
        'unit': 'N/mm',
    }
    
    # Weld capacity
    # Rn = 0.6 × FEXX × a (per unit length)
    Fnw = 0.6 * FEXX  # Nominal weld stress
    Rn = Fnw * a  # N/mm per weld
    Ra = Rn / 2.0  # ASD allowable (Ω = 2.0 for welds)
    
    results['weld_capacity'] = {
        'a': a,
        'Fnw': Fnw,
        'Rn': Rn,
        'Omega': 2.0,
        'Ra': Ra,
        'ref': 'AISC Eq. J2-3',
    }
    
    # Check
    ratio = q_per_weld / Ra if Ra > 0 else 999
    results['check'] = {
        'demand': q_per_weld,
        'capacity': Ra,
        'ratio': ratio,
        'status': 'OK' if ratio <= 1.0 else 'NG',
    }
    
    return results


def calc_actual_deflection(sec, wheel_loads, L, wheel_base):
    """
    Calculate actual deflection under crane wheel loads using influence line method
    
    Parameters:
    - wheel_loads: List of wheel loads (kN)
    - L: Span (m)
    - wheel_base: Distance between wheels (m)
    
    Returns maximum deflection in mm
    """
    E = E_STEEL  # MPa
    I = sec.Ix  # mm4
    L_mm = L * 1000  # Convert to mm
    wb_mm = wheel_base * 1000  # Convert to mm
    
    # For crane with 2 wheels, find position giving max deflection
    # Max deflection typically occurs when resultant is at a/L from one support
    # where a = distance to resultant
    
    P = sum(wheel_loads)  # Total load
    
    if len(wheel_loads) == 2:
        P1, P2 = wheel_loads[0], wheel_loads[1]
        
        # Position of resultant from first wheel
        x_resultant = (P2 * wb_mm) / P if P > 0 else wb_mm / 2
        
        # For max deflection, place resultant at L/2
        # Then first wheel is at L/2 - x_resultant
        x1_opt = L_mm / 2 - x_resultant
        x1_opt = max(0, min(x1_opt, L_mm - wb_mm))  # Keep wheels on beam
        x2_opt = x1_opt + wb_mm
        
        # Calculate deflection at midspan using superposition
        # δ = P × a × b × (L² - a² - b²) / (6 × E × I × L)
        # where a = distance from support A, b = distance from support B
        
        def deflection_at_point(x_load, x_point, P_load):
            """Single point load deflection at x_point"""
            a = x_load
            b = L_mm - x_load
            x = x_point
            
            if x <= a:
                delta = P_load * b * x * (L_mm**2 - b**2 - x**2) / (6 * E * I * L_mm)
            else:
                delta = P_load * a * (L_mm - x) * (L_mm**2 - a**2 - (L_mm - x)**2) / (6 * E * I * L_mm)
            return delta * 1000  # Convert to mm (P in N, L in mm, gives mm)
        
        # Convert kN to N
        P1_N = P1 * 1000
        P2_N = P2 * 1000
        
        # Deflection at midspan from both loads
        delta1 = deflection_at_point(x1_opt, L_mm/2, P1_N)
        delta2 = deflection_at_point(x2_opt, L_mm/2, P2_N)
        delta_max = delta1 + delta2
        
    else:
        # Single load or simplified
        P_N = P * 1000
        # Max deflection for single load at midspan
        delta_max = P_N * L_mm**3 / (48 * E * I) * 1000
    
    return abs(delta_max)


def calc_Mn(sec, Fy, Lb, cmp):
    """Standard Mn calculation for compact/noncompact sections (AISC F2/F3)"""
    Mp = Fy * sec.Zx / 1e6
    Lp, Lr = calc_Lp_Lr(sec, Fy)
    if Lb <= Lp:
        Mn = Mp
        ltb = "No LTB"
    elif Lb <= Lr:
        Mn = min(Mp - (Mp - 0.7*Fy*sec.Sx/1e6)*(Lb-Lp)/(max(Lr-Lp, 1)), Mp)
        ltb = "Inelastic LTB"
    else:
        if sec.rts > 0 and sec.Sx > 0 and sec.ho > 0:
            Fcr = math.pi**2 * E_STEEL / (Lb/sec.rts)**2 * math.sqrt(1 + 0.078*sec.J/(sec.Sx*sec.ho)*(Lb/sec.rts)**2)
        else:
            Fcr = 0.7 * Fy
        Mn = min(Fcr * sec.Sx / 1e6, Mp)
        ltb = "Elastic LTB"
    return Mn, Lp, Lr, ltb


def calc_Vn_plate_girder(sec, Fy, has_stiff=False, stiff_spa=0, use_tfa=False):
    """
    Calculate Vn for plate girders per AISC 360-16 Chapter G.
    
    For slender webs:
    - G2: Members without stiffeners
    - G3: Tension field action (with stiffeners)
    
    Parameters:
    - use_tfa: Use tension field action (requires transverse stiffeners)
    """
    Aw = sec.hw * sec.tw  # Web area (mm²)
    h_tw = sec.hw / max(sec.tw, 1)
    
    # Shear buckling coefficient kv
    kv = 5.34  # Unstiffened or a/h > 3
    if has_stiff and stiff_spa > 0 and sec.hw > 0:
        a_h = stiff_spa / sec.hw
        if a_h <= 3:
            kv = 5 + 5 / (a_h**2)
        else:
            kv = 5.34
    
    # Web shear buckling limits
    limit_1 = 1.10 * math.sqrt(kv * E_STEEL / Fy)
    limit_2 = 1.37 * math.sqrt(kv * E_STEEL / Fy)
    
    # Cv1 - Shear coefficient without tension field action (G2-3, G2-4, G2-5)
    if h_tw <= limit_1:
        Cv1 = 1.0
    elif h_tw <= limit_2:
        Cv1 = limit_1 / h_tw
    else:
        Cv1 = 1.51 * kv * E_STEEL / (h_tw**2 * Fy)
    
    # Nominal shear strength without TFA
    Vn1 = 0.6 * Fy * Aw * Cv1 / 1000  # kN
    
    # Tension Field Action (G3) - only if stiffeners present
    if use_tfa and has_stiff and stiff_spa > 0 and Cv1 < 1.0:
        a_h = stiff_spa / sec.hw
        if a_h <= 3 and a_h >= 0.5:  # TFA applicable range
            # Cv2 for tension field (G2-9)
            if h_tw <= limit_1:
                Cv2 = 1.0
            else:
                Cv2 = limit_1 / h_tw
            
            # Tension field contribution (G3-1)
            Vn_tfa = 0.6 * Fy * Aw * (Cv2 + (1 - Cv2) / (1.15 * math.sqrt(1 + a_h**2))) / 1000
            Vn = max(Vn1, Vn_tfa)
        else:
            Vn = Vn1
    else:
        Vn = Vn1
    
    return Vn, Cv1


def calc_Vn(sec, Fy, has_stiff=False, stiff_spa=0):
    """Legacy shear calculation - calls plate girder version"""
    Vn, Cv = calc_Vn_plate_girder(sec, Fy, has_stiff, stiff_spa, use_tfa=False)
    return Vn, Cv


def check_transverse_stiffener(sec, Fy, stiff_data):
    """
    Check transverse stiffener requirements per AISC G2.2
    
    Returns dict with check results
    """
    results = {'ok': True, 'checks': [], 'Ist_req': 0, 'Ist_prov': 0}
    
    if not stiff_data.get('has_transverse', False):
        return results
    
    a = stiff_data['trans_spacing']  # mm
    t_st = stiff_data['trans_t']  # mm
    b_st = stiff_data['trans_b']  # mm
    hw = sec.hw
    tw = sec.tw
    
    if a <= 0 or hw <= 0:
        return results
    
    a_h = a / hw
    
    # (1) Width-to-thickness ratio (G2-12)
    # b_st/t_st <= 0.56√(E/Fy)
    bt_limit = 0.56 * math.sqrt(E_STEEL / Fy)
    bt_ratio = b_st / t_st
    bt_ok = bt_ratio <= bt_limit
    results['checks'].append({
        'name': 'Width/Thickness',
        'demand': f"{bt_ratio:.1f}",
        'capacity': f"{bt_limit:.1f}",
        'ok': bt_ok
    })
    
    # (2) Minimum moment of inertia (G2-13)
    # Ist >= Ist1 = b*tw³*j
    j = max(2.5 / (a_h**2) - 2, 0.5)
    Ist1 = b_st * tw**3 * j  # mm⁴
    
    # For tension field action (G2-14)
    # Ist >= Ist2 = (h⁴*ρst^1.3) / (40) * (Fyw/E)^1.5
    Fyw = Fy  # Web yield stress
    rho_st = max(Fyw / Fy, 1.0)  # Stiffener yield ratio
    Ist2 = (hw**4 * rho_st**1.3) / 40 * (Fyw / E_STEEL)**1.5
    
    Ist_req = max(Ist1, Ist2)
    
    # Provided moment of inertia (single plate stiffener on one side)
    # For pair of stiffeners: I = 2 * (1/12 * t * b³ + t*b*(b/2 + tw/2)²)
    # For single stiffener: I = 1/12 * t * b³
    Ist_prov = (1/12) * t_st * b_st**3 + t_st * b_st * (b_st/2)**2  # About web face
    
    results['Ist_req'] = Ist_req
    results['Ist_prov'] = Ist_prov
    
    I_ok = Ist_prov >= Ist_req
    results['checks'].append({
        'name': 'Moment of Inertia',
        'demand': f"{Ist_req/1e4:.1f} cm⁴",
        'capacity': f"{Ist_prov/1e4:.1f} cm⁴",
        'ok': I_ok
    })
    
    # (3) Minimum stiffener width (practical)
    b_min = hw / 30 + tw  # Practical minimum
    b_ok = b_st >= b_min
    results['checks'].append({
        'name': 'Min Width',
        'demand': f"{b_min:.0f} mm",
        'capacity': f"{b_st:.0f} mm",
        'ok': b_ok
    })
    
    results['ok'] = bt_ok and I_ok and b_ok
    return results


def check_bearing_stiffener(sec, Fy, Pu, stiff_data, at_support=True):
    """
    Check bearing stiffener as a column per AISC J10.8
    
    Parameters:
    - Pu: Factored concentrated load (kN)
    - at_support: True for end bearing, False for interior
    
    Returns dict with check results
    """
    results = {'ok': True, 'checks': [], 'Pn': 0, 'ratio': 0}
    
    if not stiff_data.get('has_bearing', False):
        return results
    
    t_st = stiff_data['bearing_t']  # mm
    b_st = stiff_data['bearing_b']  # mm
    hw = sec.hw
    tw = sec.tw
    
    # (1) Width-to-thickness ratio (J10-1)
    # b_st/t_st <= 0.56√(E/Fy)
    bt_limit = 0.56 * math.sqrt(E_STEEL / Fy)
    bt_ratio = b_st / t_st
    bt_ok = bt_ratio <= bt_limit
    results['checks'].append({
        'name': 'Width/Thickness',
        'demand': f"{bt_ratio:.1f}",
        'capacity': f"{bt_limit:.1f}",
        'ok': bt_ok
    })
    
    # (2) Column check - effective section
    # Effective web width: 25*tw at ends, 12*tw each side at interior
    if at_support:
        web_eff = 25 * tw  # mm (at end)
    else:
        web_eff = 12 * tw * 2  # mm (interior, both sides)
    
    # Effective area (pair of stiffeners + web)
    A_st = 2 * b_st * t_st  # Both stiffeners
    A_web = web_eff * tw
    A_eff = A_st + A_web
    
    # Moment of inertia about web centerline
    # I = 2 * [1/12*t*b³ + t*b*(b/2 + tw/2)²] + 1/12*web_eff*tw³
    I_st = 2 * ((1/12) * t_st * b_st**3 + t_st * b_st * (b_st/2 + tw/2)**2)
    I_web = (1/12) * web_eff * tw**3
    I_eff = I_st + I_web
    
    # Radius of gyration
    r = math.sqrt(I_eff / A_eff) if A_eff > 0 else 1
    
    # Effective length (0.75*hw for bearing stiffeners)
    K = 0.75
    L_eff = K * hw
    
    # Slenderness
    KL_r = L_eff / r
    
    # Column capacity per AISC E3
    Fe = math.pi**2 * E_STEEL / KL_r**2 if KL_r > 0 else Fy
    if KL_r <= 4.71 * math.sqrt(E_STEEL / Fy):
        Fcr = Fy * (0.658**(Fy/Fe))
    else:
        Fcr = 0.877 * Fe
    
    Pn = Fcr * A_eff / 1000  # kN (nominal)
    Omega = 2.00  # ASD safety factor for compression
    Pa = Pn / Omega  # Allowable
    
    results['Pn'] = Pn
    results['Pa'] = Pa
    results['ratio'] = Pu / Pa if Pa > 0 else 999
    
    results['checks'].append({
        'name': 'Column Capacity',
        'demand': f"{Pu:.1f} kN",
        'capacity': f"{Pa:.1f} kN",
        'ok': Pu <= Pa
    })
    
    # (3) Bearing check on contact area
    # Assume 1mm clip at web-flange junction
    clip = 25  # mm typical clip
    A_bearing = 2 * (b_st - clip) * t_st
    Pb = 1.8 * Fy * A_bearing / 1000 / 2.00  # ASD bearing capacity
    
    bear_ok = Pu <= Pb
    results['checks'].append({
        'name': 'Bearing',
        'demand': f"{Pu:.1f} kN",
        'capacity': f"{Pb:.1f} kN",
        'ok': bear_ok
    })
    
    results['ok'] = bt_ok and (Pu <= Pa) and bear_ok
    return results


def check_longitudinal_stiffener(sec, Fy, stiff_data):
    """
    Check longitudinal stiffener per AISC F5 and practical requirements.
    
    Longitudinal stiffeners increase the web bend-buckling resistance.
    
    Returns dict with check results
    """
    results = {'ok': True, 'checks': [], 'Icr': 0, 'Il_prov': 0}
    
    if not stiff_data.get('has_longitudinal', False):
        return results
    
    t_st = stiff_data['long_t']  # mm
    b_st = stiff_data['long_b']  # mm
    position = stiff_data['long_position']  # fraction of hw from compression flange
    hw = sec.hw
    tw = sec.tw
    
    # (1) Width-to-thickness ratio
    bt_limit = 0.56 * math.sqrt(E_STEEL / Fy)
    bt_ratio = b_st / t_st
    bt_ok = bt_ratio <= bt_limit
    results['checks'].append({
        'name': 'Width/Thickness',
        'demand': f"{bt_ratio:.1f}",
        'capacity': f"{bt_limit:.1f}",
        'ok': bt_ok
    })
    
    # (2) Minimum moment of inertia per AISC Commentary F5
    # For single longitudinal stiffener at 0.2h from compression flange
    # Il >= h*tw³ * 2.4*(a/h)² - 0.13
    # Simplified requirement
    Icr = hw * tw**3 * 2.4  # Minimum requirement (simplified)
    
    # Provided moment of inertia
    Il_prov = (1/12) * t_st * b_st**3
    
    results['Icr'] = Icr
    results['Il_prov'] = Il_prov
    
    I_ok = Il_prov >= Icr * 0.5  # Allow 50% for practical purposes
    results['checks'].append({
        'name': 'Moment of Inertia',
        'demand': f"{Icr/1e4:.2f} cm⁴",
        'capacity': f"{Il_prov/1e4:.2f} cm⁴",
        'ok': I_ok
    })
    
    # (3) Position check (should be in compression zone)
    pos_ok = 0.1 <= position <= 0.4
    results['checks'].append({
        'name': 'Position (0.1-0.4×hw)',
        'demand': f"{position:.2f}",
        'capacity': "0.1-0.4",
        'ok': pos_ok
    })
    
    results['ok'] = bt_ok and I_ok and pos_ok
    return results


def check_wly(sec, Fy, lb, at_sup=False):
    k = sec.tf_top + 5
    return Fy * sec.tw * ((2.5 if at_sup else 5)*k + lb) / 1000


def check_wcr(sec, Fy, lb, at_sup=False):
    d, tf, tw = sec.d, sec.tf_top, sec.tw
    if d <= 0 or tf <= 0 or tw <= 0:
        return 999999
    if at_sup and lb/d <= 0.2:
        return 0.4*tw**2*(1+3*(lb/d)*(tw/tf)**1.5)*math.sqrt(E_STEEL*Fy*tf/tw)/1000
    elif at_sup:
        return 0.4*tw**2*(1+(4*lb/d-0.2)*(tw/tf)**1.5)*math.sqrt(E_STEEL*Fy*tf/tw)/1000
    else:
        return 0.8*tw**2*(1+3*(lb/d)*(tw/tf)**1.5)*math.sqrt(E_STEEL*Fy*tf/tw)/1000


def calc_defl(sec, P, L, a):
    L_mm, a_mm, P_N = L*1000, a*1000, P*1000
    if sec.Ix <= 0:
        return 9999
    if a_mm < L_mm:
        return P_N * L_mm**3 / (48*E_STEEL*sec.Ix) * (3 - 4*(a_mm/(2*L_mm))**2)
    else:
        return P_N * L_mm**3 / (48*E_STEEL*sec.Ix)


def check_fatigue(sec, M, N, cat='E'):
    if sec.Sx <= 0:
        return {'sr': 0, 'Fsr': 999, 'ratio': 0}
    sr = M * 1e6 / sec.Sx
    cf = FATIGUE_CATS.get(cat, FATIGUE_CATS['E'])
    Fsr = max(cf['thresh'], (cf['Cf']/max(N, 1))**(1/3))
    return {'sr': sr, 'Fsr': Fsr, 'ratio': sr/max(Fsr, 1)}


def draw_beam_elevation(sec, beam_span, stiff_data):
    """
    Draw beam elevation showing depth and all stiffeners arrangement.
    
    Parameters:
    - sec: Section object
    - beam_span: Beam span in meters
    - stiff_data: Dictionary with stiffener information
    """
    fig = go.Figure()
    
    L = beam_span * 1000  # Convert to mm for drawing, then scale
    d = sec.d  # Beam depth in mm
    
    # Scale factors for display
    scale_x = 1000  # Display L in meters
    scale_y = 1  # Keep mm for depth
    
    L_disp = L / scale_x  # Beam length in display units (m)
    d_disp = d / scale_y  # Beam depth in display units (mm)
    
    # Colors
    beam_color = 'rgb(70, 130, 180)'  # Steel blue
    stiff_color = 'rgb(255, 140, 0)'  # Orange for transverse
    bearing_color = 'rgb(220, 20, 60)'  # Crimson for bearing
    long_color = 'rgb(34, 139, 34)'  # Forest green for longitudinal
    
    # Draw beam outline (rectangle)
    # Top flange
    fig.add_shape(type="rect",
                  x0=0, y0=d_disp - sec.tf_top, x1=L_disp, y1=d_disp,
                  line=dict(color=beam_color, width=2),
                  fillcolor='rgba(70, 130, 180, 0.3)')
    
    # Bottom flange
    fig.add_shape(type="rect",
                  x0=0, y0=0, x1=L_disp, y1=sec.tf_bot,
                  line=dict(color=beam_color, width=2),
                  fillcolor='rgba(70, 130, 180, 0.3)')
    
    # Web
    fig.add_shape(type="rect",
                  x0=0, y0=sec.tf_bot, x1=L_disp, y1=d_disp - sec.tf_top,
                  line=dict(color=beam_color, width=1),
                  fillcolor='rgba(70, 130, 180, 0.1)')
    
    # Draw supports (triangles)
    support_size = d_disp * 0.15
    # Left support
    fig.add_trace(go.Scatter(
        x=[0, -support_size/scale_x/10, support_size/scale_x/10, 0],
        y=[-support_size*0.3, -support_size, -support_size, -support_size*0.3],
        mode='lines', fill='toself',
        fillcolor='gray', line=dict(color='black', width=1),
        showlegend=False
    ))
    # Right support
    fig.add_trace(go.Scatter(
        x=[L_disp, L_disp - support_size/scale_x/10, L_disp + support_size/scale_x/10, L_disp],
        y=[-support_size*0.3, -support_size, -support_size, -support_size*0.3],
        mode='lines', fill='toself',
        fillcolor='gray', line=dict(color='black', width=1),
        showlegend=False
    ))
    
    # === DRAW STIFFENERS ===
    stiff_positions = []  # Track all stiffener positions for labeling
    
    # 1. Bearing Stiffeners at Supports
    if stiff_data.get('has_bearing', False) and stiff_data.get('bearing_at_support', False):
        bearing_b = stiff_data['bearing_b'] / scale_x / 50  # Scale width for display
        # Left support bearing stiffener
        fig.add_shape(type="rect",
                      x0=0, y0=sec.tf_bot, x1=bearing_b, y1=d_disp - sec.tf_top,
                      line=dict(color=bearing_color, width=2),
                      fillcolor='rgba(220, 20, 60, 0.5)')
        # Right support bearing stiffener
        fig.add_shape(type="rect",
                      x0=L_disp - bearing_b, y0=sec.tf_bot, x1=L_disp, y1=d_disp - sec.tf_top,
                      line=dict(color=bearing_color, width=2),
                      fillcolor='rgba(220, 20, 60, 0.5)')
        stiff_positions.append({'x': 0, 'type': 'Bearing', 'color': bearing_color})
        stiff_positions.append({'x': L_disp, 'type': 'Bearing', 'color': bearing_color})
    
    # 2. Transverse Stiffeners (Intermediate)
    if stiff_data.get('has_transverse', False):
        spacing = stiff_data['trans_spacing']  # mm
        spacing_disp = spacing / scale_x  # Convert to display units
        trans_b = stiff_data['trans_b'] / scale_x / 50  # Scale width
        
        # Calculate number of stiffeners
        n_spaces = int(L / spacing)
        if n_spaces > 0:
            actual_spacing = L_disp / n_spaces
            for i in range(1, n_spaces):
                x_pos = i * actual_spacing
                fig.add_shape(type="rect",
                              x0=x_pos - trans_b/2, y0=sec.tf_bot,
                              x1=x_pos + trans_b/2, y1=d_disp - sec.tf_top,
                              line=dict(color=stiff_color, width=1.5),
                              fillcolor='rgba(255, 140, 0, 0.5)')
                stiff_positions.append({'x': x_pos, 'type': 'Transverse', 'color': stiff_color})
    
    # 3. Longitudinal Stiffener
    if stiff_data.get('has_longitudinal', False):
        long_pos = stiff_data['long_position']  # Fraction of hw from top
        y_long = d_disp - sec.tf_top - long_pos * sec.hw
        long_t = stiff_data['long_t'] / scale_y  # Thickness in display
        
        fig.add_shape(type="rect",
                      x0=0, y0=y_long - long_t/2, x1=L_disp, y1=y_long + long_t/2,
                      line=dict(color=long_color, width=2),
                      fillcolor='rgba(34, 139, 34, 0.5)')
    
    # Dimension annotations
    # Span dimension
    fig.add_annotation(x=L_disp/2, y=-d_disp*0.35,
                      text=f"L = {beam_span:.1f} m",
                      showarrow=False, font=dict(size=12, color='black'))
    
    # Depth dimension
    fig.add_annotation(x=L_disp + L_disp*0.05, y=d_disp/2,
                      text=f"d = {sec.d:.0f} mm",
                      showarrow=False, font=dict(size=10, color='black'),
                      textangle=-90)
    
    # Stiffener spacing annotation
    if stiff_data.get('has_transverse', False):
        spacing = stiff_data['trans_spacing']
        fig.add_annotation(x=L_disp/2, y=d_disp + d_disp*0.1,
                          text=f"Transverse stiffeners @ {spacing:.0f} mm c/c",
                          showarrow=False, font=dict(size=9, color=stiff_color))
    
    # Legend
    legend_items = []
    if stiff_data.get('has_bearing', False):
        legend_items.append(f"<span style='color:{bearing_color}'>■</span> Bearing Stiffeners")
    if stiff_data.get('has_transverse', False):
        legend_items.append(f"<span style='color:{stiff_color}'>■</span> Transverse Stiffeners")
    if stiff_data.get('has_longitudinal', False):
        legend_items.append(f"<span style='color:{long_color}'>■</span> Longitudinal Stiffener")
    
    # Update layout
    fig.update_layout(
        title=dict(text="Beam Elevation - Stiffener Arrangement", font=dict(size=14)),
        height=350,
        xaxis=dict(
            title="Length (m)",
            showgrid=True,
            gridcolor='lightgray',
            zeroline=False,
            range=[-L_disp*0.1, L_disp*1.15]
        ),
        yaxis=dict(
            title="Depth (mm)",
            showgrid=True,
            gridcolor='lightgray',
            zeroline=False,
            scaleanchor="x",
            scaleratio=1/(L_disp/d_disp) * 0.3,  # Exaggerate depth for visibility
            range=[-d_disp*0.4, d_disp*1.25]
        ),
        showlegend=False,
        margin=dict(l=50, r=50, t=50, b=50),
        plot_bgcolor='white'
    )
    
    return fig


def gen_plate_girder_calcs(sec, Fy, Fu, Lb, has_stiff, stiff_spa, weld_size=6, V_design=0, cranes=None):
    """
    Generate comprehensive plate girder design calculations per AISC 360-16
    Returns detailed results for all checks
    """
    results = {}
    
    # ========== 1. WEB SLENDERNESS & PROPORTIONING (F13.2) ==========
    h_tw = sec.hw / sec.tw
    
    # Limits
    limit_unstiff = 260  # Without transverse stiffeners
    limit_stiff = min(11.7 * math.sqrt(E_STEEL / Fy), 270)  # With stiffeners
    lambda_rw = 5.70 * math.sqrt(E_STEEL / Fy)  # Noncompact/slender boundary
    
    web_classification = 'Compact' if h_tw <= 3.76 * math.sqrt(E_STEEL/Fy) else \
                        ('Noncompact' if h_tw <= lambda_rw else 'Slender')
    
    results['web_proportions'] = {
        'h_tw': h_tw,
        'limit_unstiff': limit_unstiff,
        'limit_stiff': limit_stiff,
        'lambda_rw': lambda_rw,
        'classification': web_classification,
        'needs_stiffeners': h_tw > limit_unstiff,
        'check_unstiff': 'OK' if h_tw <= limit_unstiff else 'NG - Stiffeners Required',
        'check_stiff': 'OK' if h_tw <= limit_stiff else 'NG - Exceeds Maximum',
    }
    
    # ========== 2. ELASTIC & PLASTIC NEUTRAL AXIS ==========
    A_tf = sec.bf_top * sec.tf_top
    A_bf = sec.bf_bot * sec.tf_bot
    A_w = sec.hw * sec.tw
    A_total = A_tf + A_bf + A_w
    
    # Elastic Neutral Axis (from bottom)
    y_tf = sec.tf_bot + sec.hw + sec.tf_top / 2
    y_bf = sec.tf_bot / 2
    y_w = sec.tf_bot + sec.hw / 2
    y_ena = (A_tf * y_tf + A_bf * y_bf + A_w * y_w) / A_total
    
    # Plastic Neutral Axis (from bottom)
    # Equal areas above and below PNA
    A_half = A_total / 2
    if A_bf >= A_half:
        y_pna = A_half / sec.bf_bot
        pna_location = 'Bottom Flange'
    elif A_bf + A_w >= A_half:
        y_pna = sec.tf_bot + (A_half - A_bf) / sec.tw
        pna_location = 'Web'
    else:
        y_pna = sec.tf_bot + sec.hw + (A_half - A_bf - A_w) / sec.bf_top
        pna_location = 'Top Flange'
    
    # Section moduli
    c_top = sec.d - y_ena
    c_bot = y_ena
    S_xc = sec.Ix / c_top  # Compression flange (top)
    S_xt = sec.Ix / c_bot  # Tension flange (bottom)
    
    # Plastic section modulus
    Z_x = sec.Zx  # Use pre-calculated value
    
    results['neutral_axis'] = {
        'A_tf': A_tf,
        'A_bf': A_bf,
        'A_w': A_w,
        'A_total': A_total,
        'y_ena': y_ena,
        'y_pna': y_pna,
        'pna_location': pna_location,
        'c_top': c_top,
        'c_bot': c_bot,
        'S_xc': S_xc,
        'S_xt': S_xt,
        'Z_x': Z_x,
    }
    
    # ========== 3. FLEXURE - PLATE GIRDER PARAMETERS ==========
    # aw = web area / compression flange area
    Afc = sec.bf_top * sec.tf_top
    aw = A_w / max(Afc, 1)
    aw = min(aw, 10)  # Limit per F4
    
    # hc = twice distance from centroid to inside of compression flange
    hc = 2 * (sec.d - y_ena - sec.tf_top)
    hc = max(hc, sec.hw)
    
    # Rpg = bending strength reduction factor (F5-6)
    if web_classification == 'Slender':
        Rpg = 1 - aw / (1200 + 300 * aw) * (hc / sec.tw - 5.7 * math.sqrt(E_STEEL / Fy))
        Rpg = min(max(Rpg, 0.5), 1.0)
    else:
        Rpg = 1.0
    
    results['flexure_params'] = {
        'aw': aw,
        'hc': hc,
        'Rpg': Rpg,
    }
    
    # ========== 4. TENSION FLANGE YIELDING (F4.3/F5.3) ==========
    Mn_tfy = Fy * S_xt / 1e6
    tfy_governs = S_xt < S_xc
    
    results['tension_flange_yielding'] = {
        'Mn': Mn_tfy,
        'S_xt': S_xt,
        'governs': tfy_governs,
        'ref': 'AISC F4-15 / F5-10',
    }
    
    # ========== 5. COMPRESSION FLANGE YIELDING (F4.1/F5.1) ==========
    Mn_cfy = Rpg * Fy * S_xc / 1e6
    
    results['compression_flange_yielding'] = {
        'Mn': Mn_cfy,
        'Rpg': Rpg,
        'S_xc': S_xc,
        'ref': 'AISC F5-1' if web_classification == 'Slender' else 'AISC F4-1',
    }
    
    # ========== 6. LATERAL-TORSIONAL BUCKLING (F4.2/F5.2) ==========
    Lp, Lr = calc_Lp_Lr(sec, Fy)
    
    if Lb <= Lp:
        Mn_ltb = Rpg * Fy * S_xc / 1e6
        ltb_type = 'No LTB (Lb ≤ Lp)'
        Fcr_ltb = Fy
    elif Lb <= Lr:
        Cb = 1.0  # Conservative
        Mn_ltb = Cb * (Rpg * Fy * S_xc / 1e6 - (Rpg * Fy * S_xc / 1e6 - 0.7 * Rpg * Fy * S_xc / 1e6) * (Lb - Lp) / (Lr - Lp))
        Mn_ltb = min(Mn_ltb, Rpg * Fy * S_xc / 1e6)
        ltb_type = 'Inelastic LTB (Lp < Lb ≤ Lr)'
        Fcr_ltb = Mn_ltb * 1e6 / S_xc / Rpg
    else:
        if sec.rts > 0 and sec.Sx > 0 and sec.ho > 0:
            Fcr_ltb = math.pi**2 * E_STEEL / (Lb / sec.rts)**2 * math.sqrt(1 + 0.078 * sec.J / (sec.Sx * sec.ho) * (Lb / sec.rts)**2)
        else:
            Fcr_ltb = 0.7 * Fy
        Mn_ltb = Rpg * Fcr_ltb * S_xc / 1e6
        ltb_type = 'Elastic LTB (Lb > Lr)'
    
    results['lateral_torsional_buckling'] = {
        'Lp': Lp,
        'Lr': Lr,
        'Lb': Lb,
        'Cb': 1.0,
        'Fcr': Fcr_ltb,
        'Mn': Mn_ltb,
        'type': ltb_type,
        'ref': 'AISC F5-2/F5-3/F5-4' if web_classification == 'Slender' else 'AISC F4-2',
    }
    
    # ========== 7. COMPRESSION FLANGE LOCAL BUCKLING (F4.3/F5.7-9) ==========
    lambda_f = sec.bf_top / (2 * sec.tf_top)
    lambda_pf = 0.38 * math.sqrt(E_STEEL / Fy)
    lambda_rf = 0.95 * math.sqrt(E_STEEL / (0.7 * Fy))
    
    if lambda_f <= lambda_pf:
        Mn_flb = Rpg * Fy * S_xc / 1e6
        flb_type = 'Compact (λf ≤ λpf)'
    elif lambda_f <= lambda_rf:
        Mn_flb = Rpg * (Fy - 0.3 * Fy * (lambda_f - lambda_pf) / (lambda_rf - lambda_pf)) * S_xc / 1e6
        flb_type = 'Noncompact (λpf < λf ≤ λrf)'
    else:
        Fcr_flb = 0.9 * E_STEEL / lambda_f**2
        Mn_flb = Rpg * Fcr_flb * S_xc / 1e6
        flb_type = 'Slender (λf > λrf)'
    
    results['compression_flange_local_buckling'] = {
        'lambda_f': lambda_f,
        'lambda_pf': lambda_pf,
        'lambda_rf': lambda_rf,
        'Mn': Mn_flb,
        'type': flb_type,
        'ref': 'AISC F5-7/F5-8/F5-9',
    }
    
    # ========== 8. GOVERNING FLEXURAL STRENGTH ==========
    Mn_values = [Mn_cfy, Mn_ltb, Mn_flb]
    if tfy_governs:
        Mn_values.append(Mn_tfy)
    
    Mn_gov = min(Mn_values)
    
    if Mn_gov == Mn_cfy:
        gov_limit_state = 'Compression Flange Yielding'
    elif Mn_gov == Mn_ltb:
        gov_limit_state = 'Lateral-Torsional Buckling'
    elif Mn_gov == Mn_flb:
        gov_limit_state = 'Compression Flange Local Buckling'
    else:
        gov_limit_state = 'Tension Flange Yielding'
    
    results['flexure_governing'] = {
        'Mn': Mn_gov,
        'limit_state': gov_limit_state,
        'Ma': Mn_gov / 1.67,
    }
    
    # ========== 9. SHEAR STRENGTH - END PANELS (G2) ==========
    # End panels - no tension field action
    Aw = sec.hw * sec.tw
    kv_end = 5.34  # Unstiffened or end panel
    
    limit1 = 1.10 * math.sqrt(kv_end * E_STEEL / Fy)
    limit2 = 1.37 * math.sqrt(kv_end * E_STEEL / Fy)
    
    if h_tw <= limit1:
        Cv_end = 1.0
    elif h_tw <= limit2:
        Cv_end = limit1 / h_tw
    else:
        Cv_end = 1.51 * kv_end * E_STEEL / (h_tw**2 * Fy)
    
    Vn_end = 0.6 * Fy * Aw * Cv_end / 1000  # kN
    
    results['shear_end_panel'] = {
        'kv': kv_end,
        'Cv': Cv_end,
        'Vn': Vn_end,
        'Va': Vn_end / 1.50,
        'ref': 'AISC G2.1 (No TFA)',
        'note': 'End panels - Tension field action not permitted',
    }
    
    # ========== 10. SHEAR STRENGTH - INTERIOR PANELS (G3) ==========
    if has_stiff and stiff_spa > 0:
        a = stiff_spa * 1000  # mm
        a_h = a / sec.hw
        
        if a_h <= 3.0:
            kv_int = 5 + 5 / (a_h**2)
        else:
            kv_int = 5.34
        
        # Check if TFA can be used
        # TFA not permitted if: a/h > 3.0 or a/h > [260/(h/tw)]²
        tfa_limit = (260 / h_tw)**2
        can_use_tfa = (a_h <= 3.0) and (a_h <= tfa_limit) and (h_tw > 1.10 * math.sqrt(kv_int * E_STEEL / Fy))
        
        if can_use_tfa:
            # With Tension Field Action (G3)
            Cv2 = 1.51 * kv_int * E_STEEL / (h_tw**2 * Fy) if h_tw > 1.10 * math.sqrt(kv_int * E_STEEL / Fy) else 1.0
            
            # TFA contribution
            Vn_int = 0.6 * Fy * Aw * (Cv2 + (1 - Cv2) / (1.15 * math.sqrt(1 + a_h**2))) / 1000
            tfa_used = True
        else:
            # Without TFA
            limit1_int = 1.10 * math.sqrt(kv_int * E_STEEL / Fy)
            limit2_int = 1.37 * math.sqrt(kv_int * E_STEEL / Fy)
            
            if h_tw <= limit1_int:
                Cv_int = 1.0
            elif h_tw <= limit2_int:
                Cv_int = limit1_int / h_tw
            else:
                Cv_int = 1.51 * kv_int * E_STEEL / (h_tw**2 * Fy)
            
            Vn_int = 0.6 * Fy * Aw * Cv_int / 1000
            tfa_used = False
            Cv2 = Cv_int
        
        results['shear_interior_panel'] = {
            'a': a,
            'a_h': a_h,
            'kv': kv_int,
            'Cv2': Cv2,
            'Vn': Vn_int,
            'Va': Vn_int / 1.50,
            'tfa_used': tfa_used,
            'ref': 'AISC G3 (With TFA)' if tfa_used else 'AISC G2.1 (No TFA)',
        }
    else:
        results['shear_interior_panel'] = {
            'note': 'No interior panels (no transverse stiffeners)',
            'Vn': Vn_end,
            'Va': Vn_end / 1.50,
        }
    
    # ========== 11. WELD DESIGN ==========
    t_flange = min(sec.tf_top, sec.tf_bot)
    w_min = check_minimum_weld_size(sec.tw, t_flange)
    w_max = sec.tw - 2  # 2mm less than thinner part
    
    # Shear flow at web-flange junction
    Q = sec.bf_top * sec.tf_top * (sec.d - y_ena - sec.tf_top/2)  # First moment of area
    q = V_design * 1000 * Q / sec.Ix if sec.Ix > 0 else 0  # N/mm (shear flow)
    
    # Weld capacity
    a_weld = 0.707 * weld_size  # Effective throat
    FEXX = 482  # E70 electrode (MPa)
    Fnw = 0.6 * FEXX
    Rn_weld = Fnw * a_weld * 2  # Two welds (both sides)
    Ra_weld = Rn_weld / 2.0  # ASD (Omega = 2.0)
    
    results['weld_design'] = {
        'w_min': w_min,
        'w_max': w_max,
        'w_provided': weld_size,
        'size_check': 'OK' if w_min <= weld_size <= w_max else 'NG',
        'Q': Q,
        'q': q,
        'q_per_weld': q / 2,
        'a_throat': a_weld,
        'FEXX': FEXX,
        'Rn': Rn_weld,
        'Ra': Ra_weld,
        'stress_ratio': q / Ra_weld if Ra_weld > 0 else 999,
        'stress_check': 'OK' if q <= Ra_weld else 'NG',
        'ref': 'AISC J2.4 & J2.2',
    }
    
    # ========== 12. STIFFENER REQUIREMENTS ==========
    if has_stiff and stiff_spa > 0:
        # Transverse stiffener requirements (G2.2)
        a = stiff_spa * 1000
        a_h = a / sec.hw
        
        # Minimum moment of inertia (G2.2)
        j = max(2.5 / a_h**2 - 2, 0.5)
        Ist_min1 = sec.hw * sec.tw**3 * j
        
        # For TFA (if applicable)
        Fyw = Fy
        Fyst = Fy  # Assume same material
        rho_st = max(Fyw / Fyst, 1.0)
        Vr = V_design * 1.50  # Required shear (unfactored × Omega)
        Vc = 0.6 * Fy * Aw * Cv_end / 1000 * 1.50 if 'Cv_end' in dir() else Vr
        
        if Vr > Vc:
            Ist_min2 = (sec.hw**4 * rho_st**1.3 / 40) * (Fyw / E_STEEL)**1.5
        else:
            Ist_min2 = 0
        
        Ist_min = max(Ist_min1, Ist_min2)
        
        results['stiffener_requirements'] = {
            'j': j,
            'Ist_min1': Ist_min1,
            'Ist_min2': Ist_min2,
            'Ist_min': Ist_min,
            'b_min': sec.hw / 30 + sec.tw,  # Minimum width
            'ref': 'AISC G2.2',
        }
    else:
        results['stiffener_requirements'] = {
            'note': 'No transverse stiffeners specified',
        }
    
    return results


def gen_detailed_calcs(sec, Fy, Fu, cmp, gov, L, crane_cls, fat_cat, Lb, has_stiff, stiff_spa, 
                        cranes, w_self, R_self, M_self, V_self, M_lat, ratios, weld_size=6, delta_actual=0):
    """
    Generate comprehensive detailed calculations with all equations and code references.
    Returns a list of sections with calculations
    """
    calcs = []
    
    # Get plate girder detailed results
    V_design = ratios.get('V_total', V_self + (gov['shear'].V_max if gov and gov.get('shear') else 0))
    pg_results = gen_plate_girder_calcs(sec, Fy, Fu, Lb, has_stiff, stiff_spa, weld_size, V_design, cranes)
    
    # ========== 1. SECTION PROPERTIES ==========
    calcs.append({
        'title': '1. SECTION PROPERTIES',
        'ref': 'AISC 360-16, Section B4',
        'content': [
            ('Section Designation', f"**{sec.name}** ({sec.sec_type.replace('_', ' ').title()})"),
            ('Total Depth', f"$d = {sec.d:.0f}$ mm"),
            ('Web Height', f"$h_w = {sec.hw:.0f}$ mm"),
            ('Web Thickness', f"$t_w = {sec.tw:.0f}$ mm"),
            ('Top Flange', f"$b_{{f,top}} \\times t_{{f,top}} = {sec.bf_top:.0f} \\times {sec.tf_top:.0f}$ mm"),
            ('Bottom Flange', f"$b_{{f,bot}} \\times t_{{f,bot}} = {sec.bf_bot:.0f} \\times {sec.tf_bot:.0f}$ mm"),
        ],
        'calculations': [
            ('Cross-sectional Area', 
             f"$A = b_{{f,top}} \\cdot t_{{f,top}} + h_w \\cdot t_w + b_{{f,bot}} \\cdot t_{{f,bot}}$",
             f"$A = {sec.bf_top:.0f} \\times {sec.tf_top:.0f} + {sec.hw:.0f} \\times {sec.tw:.0f} + {sec.bf_bot:.0f} \\times {sec.tf_bot:.0f} = {sec.A:.0f}$ mm²"),
            ('Moment of Inertia (Strong Axis)',
             f"$I_x = \\sum (I_{{local}} + A_i \\cdot d_i^2)$",
             f"$I_x = {sec.Ix:.2e}$ mm⁴ = {sec.Ix/1e6:.2f} × 10⁶ mm⁴"),
            ('Elastic Section Modulus',
             f"$S_x = \\frac{{I_x}}{{c}}$ where $c$ = distance to extreme fiber",
             f"$S_x = \\frac{{{sec.Ix:.2e}}}{{{sec.d - sec.y_bar:.1f}}} = {sec.Sx:.0f}$ mm³ = {sec.Sx/1e3:.1f} × 10³ mm³"),
            ('Plastic Section Modulus',
             f"$C_w = {sec.Cw:.2e}$ mm⁶"),
            ('Effective Radius of Gyration for LTB',
             f"$r_{{ts}} = \\sqrt{{\\frac{{\\sqrt{{I_y \\cdot C_w}}}}{{S_x}}}}$",
             f"$r_{{ts}} = {sec.rts:.1f}$ mm"),
            ('Unit Weight',
             f"$w = A \\cdot \\rho_{{steel}}$",
             f"$w = {sec.A:.0f} \\times 7850 / 10^6 = {sec.mass:.1f}$ kg/m"),
        ]
    })
    
    # ========== 2. MATERIAL PROPERTIES ==========
    calcs.append({
        'title': '2. MATERIAL PROPERTIES',
        'ref': 'AISC 360-16, Table 2-4',
        'content': [
            ('Yield Strength', f"$F_y = {Fy}$ MPa"),
            ('Ultimate Tensile Strength', f"$F_u = {Fu}$ MPa"),
            ('Modulus of Elasticity', f"$E = {E_STEEL}$ MPa"),
            ('Shear Modulus', f"$G = {G_STEEL}$ MPa"),
        ],
        'calculations': []
    })
    
    # ========== 3. COMPACTNESS CHECK ==========
    lpf = 0.38 * math.sqrt(E_STEEL / Fy)
    lrf = 1.0 * math.sqrt(E_STEEL / Fy)
    lpw = 3.76 * math.sqrt(E_STEEL / Fy)
    lrw = 5.70 * math.sqrt(E_STEEL / Fy)
    
    calcs.append({
        'title': '3. COMPACTNESS CHECK',
        'ref': 'AISC 360-16, Table B4.1b',
        'content': [
            ('Purpose', 'Determine if section is Compact, Noncompact, or Slender for local buckling'),
        ],
        'calculations': [
            ('**Flange Slenderness:**', '', ''),
            ('Width-to-Thickness Ratio',
             f"$\\lambda_f = \\frac{{b_f}}{{2 \\cdot t_f}}$",
             f"$\\lambda_f = \\frac{{{sec.bf_top:.0f}}}{{2 \\times {sec.tf_top:.0f}}} = {cmp['lf']:.2f}$"),
            ('Compact Limit (λpf)',
             f"$\\lambda_{{pf}} = 0.38 \\sqrt{{\\frac{{E}}{{F_y}}}}$",
             f"$\\lambda_{{pf}} = 0.38 \\sqrt{{\\frac{{{E_STEEL}}}{{{Fy}}}}} = {lpf:.2f}$"),
            ('Noncompact Limit (λrf)',
             f"$\\lambda_{{rf}} = 1.0 \\sqrt{{\\frac{{E}}{{F_y}}}}$",
             f"$\\lambda_{{rf}} = 1.0 \\sqrt{{\\frac{{{E_STEEL}}}{{{Fy}}}}} = {lrf:.2f}$"),
            ('Flange Classification',
             f"$\\lambda_f = {cmp['lf']:.2f}$ vs $\\lambda_{{pf}} = {lpf:.2f}$",
             f"**{cmp['flg']}** ({'λf ≤ λpf' if cmp['flg'] == 'Compact' else 'λpf < λf ≤ λrf' if cmp['flg'] == 'Noncompact' else 'λf > λrf'})"),
            ('', '', ''),
            ('**Web Slenderness:**', '', ''),
            ('Width-to-Thickness Ratio',
             f"$\\lambda_w = \\frac{{h_w}}{{t_w}}$",
             f"$\\lambda_w = \\frac{{{sec.hw:.0f}}}{{{sec.tw:.0f}}} = {cmp['lw']:.2f}$"),
            ('Compact Limit (λpw)',
             f"$\\lambda_{{pw}} = 3.76 \\sqrt{{\\frac{{E}}{{F_y}}}}$",
             f"$\\lambda_{{pw}} = 3.76 \\sqrt{{\\frac{{{E_STEEL}}}{{{Fy}}}}} = {lpw:.2f}$"),
            ('Noncompact Limit (λrw)',
             f"$\\lambda_{{rw}} = 5.70 \\sqrt{{\\frac{{E}}{{F_y}}}}$",
             f"$\\lambda_{{rw}} = 5.70 \\sqrt{{\\frac{{{E_STEEL}}}{{{Fy}}}}} = {lrw:.2f}$"),
            ('Web Classification',
             f"$\\lambda_w = {cmp['lw']:.2f}$ vs $\\lambda_{{pw}} = {lpw:.2f}$",
             f"**{cmp['web']}** ({'λw ≤ λpw' if cmp['web'] == 'Compact' else 'λpw < λw ≤ λrw' if cmp['web'] == 'Noncompact' else 'λw > λrw'})"),
        ]
    })
    
    # ========== 3a. PLATE GIRDER PROPORTIONS (F13.2) - For Built-up Sections ==========
    if sec.sec_type == 'built_up':
        wp = pg_results['web_proportions']
        na = pg_results['neutral_axis']
        
        calcs.append({
            'title': '3a. PLATE GIRDER PROPORTIONS',
            'ref': 'AISC 360-16, Section F13.2',
            'content': [
                ('Purpose', 'Check web proportioning limits for plate girders'),
            ],
            'calculations': [
                ('**Web Slenderness Limits:**', '', ''),
                ('Without Stiffeners (F13.2a)',
                 f"$\\frac{{h}}{{t_w}} \\leq 260$",
                 f"${wp['h_tw']:.1f} \\leq 260$ → **{wp['check_unstiff']}**"),
                ('With Stiffeners (F13.2b)',
                 f"$\\frac{{h}}{{t_w}} \\leq 11.7\\sqrt{{\\frac{{E}}{{F_y}}}} \\leq 270$",
                 f"${wp['h_tw']:.1f} \\leq {wp['limit_stiff']:.1f}$ → **{wp['check_stiff']}**"),
                ('Web Classification',
                 f"$\\lambda_{{rw}} = 5.70\\sqrt{{E/F_y}} = {wp['lambda_rw']:.1f}$",
                 f"**{wp['classification']}** ({'Stiffeners Required' if wp['needs_stiffeners'] else 'No Stiffeners Required'})"),
                ('', '', ''),
                ('**Elastic Neutral Axis (ENA):**', '', ''),
                ('ENA from Bottom',
                 f"$\\bar{{y}}_{{ENA}} = \\frac{{\\sum A_i \\cdot y_i}}{{\\sum A_i}}$",
                 f"$\\bar{{y}}_{{ENA}} = {na['y_ena']:.1f}$ mm"),
                ('Distance to Top Fiber',
                 f"$c_{{top}} = d - \\bar{{y}}_{{ENA}}$",
                 f"$c_{{top}} = {sec.d:.0f} - {na['y_ena']:.1f} = {na['c_top']:.1f}$ mm"),
                ('Distance to Bottom Fiber',
                 f"$c_{{bot}} = \\bar{{y}}_{{ENA}}$",
                 f"$c_{{bot}} = {na['c_bot']:.1f}$ mm"),
                ('', '', ''),
                ('**Plastic Neutral Axis (PNA):**', '', ''),
                ('PNA from Bottom',
                 f"Where $A_{{above}} = A_{{below}} = A/2$",
                 f"$\\bar{{y}}_{{PNA}} = {na['y_pna']:.1f}$ mm (in {na['pna_location']})"),
                ('', '', ''),
                ('**Section Moduli:**', '', ''),
                ('Elastic (Compression)',
                 f"$S_{{xc}} = \\frac{{I_x}}{{c_{{top}}}}$",
                 f"$S_{{xc}} = {na['S_xc']:.0f}$ mm³"),
                ('Elastic (Tension)',
                 f"$S_{{xt}} = \\frac{{I_x}}{{c_{{bot}}}}$",
                 f"$S_{{xt}} = {na['S_xt']:.0f}$ mm³"),
                ('Plastic',
                 f"$Z_x$",
                 f"$Z_x = {na['Z_x']:.0f}$ mm³"),
            ]
        })
    
    # ========== 4. LOADING ==========
    mc = gov.get('moment') if gov else None
    sc = gov.get('shear') if gov else None
    rc = gov.get('reaction') if gov else None
    
    M_crane = abs(mc.M_max) if mc else 0
    V_crane = sc.V_max if sc else 0
    R_crane = max(rc.R_left, rc.R_right) if rc else 0
    
    calcs.append({
        'title': '4. DESIGN LOADS',
        'ref': 'AISC Design Guide 7, CMAA 70',
        'content': [
            ('Beam Span', f"$L = {L:.2f}$ m = {L*1000:.0f} mm"),
            ('Unbraced Length', f"$L_b = {Lb/1000:.2f}$ m = {Lb:.0f} mm"),
        ],
        'calculations': [
            ('**Crane Loads (Governing Cases):**', '', ''),
            ('Max Moment Case',
             f"{mc.desc if mc else 'N/A'}",
             f"$M_{{crane}} = {M_crane:.2f}$ kN-m @ {mc.M_pos:.2f} m" if mc else "N/A"),
            ('Max Shear Case',
             f"{sc.desc if sc else 'N/A'}",
             f"$V_{{crane}} = {V_crane:.2f}$ kN" if sc else "N/A"),
            ('Max Reaction Case',
             f"{rc.desc if rc else 'N/A'}",
             f"$R_{{crane}} = {R_crane:.2f}$ kN" if rc else "N/A"),
            ('', '', ''),
            ('**Beam Self-Weight:**', '', ''),
            ('Uniformly Distributed Load',
             f"$w_{{self}} = \\frac{{mass \\cdot g}}{{1000}}$",
             f"$w_{{self}} = \\frac{{{sec.mass:.1f} \\times 9.81}}{{1000}} = {w_self:.3f}$ kN/m"),
            ('Reaction from Self-Weight',
             f"$R_{{self}} = \\frac{{w_{{self}} \\cdot L}}{{2}}$",
             f"$R_{{self}} = \\frac{{{w_self:.3f} \\times {L:.2f}}}{{2}} = {R_self:.2f}$ kN"),
            ('Moment from Self-Weight',
             f"$M_{{self}} = \\frac{{w_{{self}} \\cdot L^2}}{{8}}$",
             f"$M_{{self}} = \\frac{{{w_self:.3f} \\times {L:.2f}^2}}{{8}} = {M_self:.2f}$ kN-m"),
            ('Shear from Self-Weight',
             f"$V_{{self}} = \\frac{{w_{{self}} \\cdot L}}{{2}}$",
             f"$V_{{self}} = {V_self:.2f}$ kN"),
            ('', '', ''),
            ('**Total Design Forces:**', '', ''),
            ('Total Moment',
             f"$M_u = M_{{crane}} + M_{{self}}$",
             f"$M_u = {M_crane:.2f} + {M_self:.2f} = {M_crane + M_self:.2f}$ kN-m"),
            ('Total Shear',
             f"$V_u = V_{{crane}} + V_{{self}}$",
             f"$V_u = {V_crane:.2f} + {V_self:.2f} = {V_crane + V_self:.2f}$ kN"),
            ('Total Reaction',
             f"$R_u = R_{{crane}} + R_{{self}}$",
             f"$R_u = {R_crane:.2f} + {R_self:.2f} = {R_crane + R_self:.2f}$ kN"),
        ]
    })
    
    # ========== 5. FLEXURAL STRENGTH ==========
    Lp, Lr = calc_Lp_Lr(sec, Fy)
    Mp = Fy * sec.Zx / 1e6
    Mr = 0.7 * Fy * sec.Sx / 1e6
    
    # Determine LTB case
    Lb_m = Lb / 1000
    if Lb <= Lp:
        ltb_case = "No LTB (Lb ≤ Lp)"
        Mn = Mp
    elif Lb <= Lr:
        ltb_case = "Inelastic LTB (Lp < Lb ≤ Lr)"
        Mn = Mp - (Mp - Mr) * (Lb - Lp) / (Lr - Lp)
        Mn = min(Mn, Mp)
    else:
        ltb_case = "Elastic LTB (Lb > Lr)"
        if sec.rts > 0 and sec.Sx > 0 and sec.ho > 0:
            Fcr = math.pi**2 * E_STEEL / (Lb/sec.rts)**2 * math.sqrt(1 + 0.078*sec.J/(sec.Sx*sec.ho)*(Lb/sec.rts)**2)
        else:
            Fcr = 0.7 * Fy
        Mn = min(Fcr * sec.Sx / 1e6, Mp)
    
    calcs.append({
        'title': '5. FLEXURAL STRENGTH',
        'ref': 'AISC 360-16, Chapter F (F2 for I-shapes)',
        'content': [
            ('Limit State', 'Lateral-Torsional Buckling (LTB) and Local Buckling'),
        ],
        'calculations': [
            ('**Plastic Moment (Eq. F2-1):**', '', ''),
            ('Plastic Moment',
             f"$M_p = F_y \\cdot Z_x$",
             f"$M_p = {Fy} \\times {sec.Zx/1e3:.1f} \\times 10^3 / 10^6 = {Mp:.2f}$ kN-m"),
            ('', '', ''),
            ('**Limiting Lengths:**', '', ''),
            ('Limiting Length Lp (Eq. F2-5)',
             f"$L_p = 1.76 \\cdot r_y \\cdot \\sqrt{{\\frac{{E}}{{F_y}}}}$",
             f"$L_p = 1.76 \\times {sec.ry:.1f} \\times \\sqrt{{\\frac{{{E_STEEL}}}{{{Fy}}}}} = {Lp:.0f}$ mm = {Lp/1000:.2f} m"),
            ('Limiting Length Lr (Eq. F2-6)',
             f"$L_r = 1.95 \\cdot r_{{ts}} \\cdot \\frac{{E}}{{0.7 F_y}} \\sqrt{{\\frac{{J \\cdot c}}{{S_x \\cdot h_o}} + \\sqrt{{\\left(\\frac{{J \\cdot c}}{{S_x \\cdot h_o}}\\right)^2 + 6.76 \\left(\\frac{{0.7 F_y}}{{E}}\\right)^2}}}}$",
             f"$L_r = {Lr:.0f}$ mm = {Lr/1000:.2f} m"),
            ('', '', ''),
            ('**LTB Check:**', '', ''),
            ('Unbraced Length',
             f"$L_b = {Lb:.0f}$ mm = {Lb/1000:.2f} m",
             f"**{ltb_case}**"),
        ]
    })
    
    # Add LTB-specific calculations
    if Lb <= Lp:
        calcs[-1]['calculations'].extend([
            ('', '', ''),
            ('**Nominal Moment (No LTB):**', '', ''),
            ('Nominal Moment',
             f"$M_n = M_p$ (Eq. F2-1)",
             f"$M_n = {Mp:.2f}$ kN-m"),
        ])
    elif Lb <= Lr:
        calcs[-1]['calculations'].extend([
            ('', '', ''),
            ('**Nominal Moment (Inelastic LTB - Eq. F2-2):**', '', ''),
            ('Nominal Moment',
             f"$M_n = C_b \\left[ M_p - (M_p - 0.7 F_y S_x) \\left( \\frac{{L_b - L_p}}{{L_r - L_p}} \\right) \\right] \\leq M_p$",
             f"$M_n = 1.0 \\times \\left[ {Mp:.2f} - ({Mp:.2f} - {Mr:.2f}) \\times \\frac{{{Lb/1000:.2f} - {Lp/1000:.2f}}}{{{Lr/1000:.2f} - {Lp/1000:.2f}}} \\right]$"),
            ('',
             f"(with $C_b = 1.0$ conservative)",
             f"$M_n = {Mn:.2f}$ kN-m"),
        ])
    else:
        Fcr = math.pi**2 * E_STEEL / (Lb/sec.rts)**2 * math.sqrt(1 + 0.078*sec.J/(sec.Sx*sec.ho)*(Lb/sec.rts)**2)
        calcs[-1]['calculations'].extend([
            ('', '', ''),
            ('**Nominal Moment (Elastic LTB - Eq. F2-3 & F2-4):**', '', ''),
            ('Critical Stress (Eq. F2-4)',
             f"$F_{{cr}} = \\frac{{C_b \\pi^2 E}}{{(L_b/r_{{ts}})^2}} \\sqrt{{1 + 0.078 \\frac{{J c}}{{S_x h_o}} \\left( \\frac{{L_b}}{{r_{{ts}}}} \\right)^2}}$",
             f"$F_{{cr}} = \\frac{{1.0 \\times \\pi^2 \\times {E_STEEL}}}{{({Lb:.0f}/{sec.rts:.1f})^2}} \\times \\sqrt{{1 + 0.078 \\times \\frac{{{sec.J:.0f}}}{{{sec.Sx:.0f} \\times {sec.ho:.0f}}} \\times ({Lb:.0f}/{sec.rts:.1f})^2}}$"),
            ('',
             f"",
             f"$F_{{cr}} = {Fcr:.2f}$ MPa"),
            ('Nominal Moment (Eq. F2-3)',
             f"$M_n = F_{{cr}} \\cdot S_x \\leq M_p$",
             f"$M_n = \\min({Fcr:.2f} \\times {sec.Sx/1e3:.1f} \\times 10^3 / 10^6, {Mp:.2f}) = {Mn:.2f}$ kN-m"),
        ])
    
    # Add allowable moment
    Omega_b = 1.67
    Ma = Mn / Omega_b
    M_total = M_crane + M_self
    ratio_flex = M_total / Ma if Ma > 0 else 999
    
    calcs[-1]['calculations'].extend([
        ('', '', ''),
        ('**Allowable Moment (ASD):**', '', ''),
        ('Safety Factor',
             f"$\\Omega_b = 1.67$ (AISC F1)",
             ""),
        ('Allowable Moment',
             f"$M_a = \\frac{{M_n}}{{\\Omega_b}}$",
             f"$M_a = \\frac{{{Mn:.2f}}}{{1.67}} = {Ma:.2f}$ kN-m"),
        ('', '', ''),
        ('**Demand/Capacity Check:**', '', ''),
        ('Flexure Ratio',
             f"$\\frac{{M_u}}{{M_a}} \\leq 1.0$",
             f"$\\frac{{{M_total:.2f}}}{{{Ma:.2f}}} = {ratio_flex:.3f}$ {'✓ OK' if ratio_flex <= 1.0 else '✗ NG'}"),
    ])
    
    # ========== 6. SHEAR STRENGTH ==========
    Aw = sec.hw * sec.tw  # Web area
    Vn, Cv = calc_Vn(sec, Fy, has_stiff, stiff_spa)
    
    # Calculate kv
    if has_stiff and stiff_spa > 0:
        a_h = (stiff_spa * 1000) / sec.hw
        if a_h <= 3.0:
            kv = 5 + 5 / (a_h ** 2)
        else:
            kv = 5.34
    else:
        kv = 5.34
    
    h_tw = sec.hw / sec.tw
    
    calcs.append({
        'title': '6. SHEAR STRENGTH',
        'ref': 'AISC 360-16, Chapter G (G2)',
        'content': [
            ('Web Area', f"$A_w = h_w \\times t_w = {sec.hw:.0f} \\times {sec.tw:.0f} = {Aw:.0f}$ mm²"),
        ],
        'calculations': [
            ('**Web Slenderness:**', '', ''),
            ('Web Slenderness Ratio',
             f"$\\frac{{h}}{{t_w}}$",
             f"$\\frac{{{sec.hw:.0f}}}{{{sec.tw:.0f}}} = {h_tw:.2f}$"),
            ('', '', ''),
            ('**Shear Buckling Coefficient (Eq. G2-5):**', '', ''),
            ('Stiffener Condition',
             f"{'With stiffeners, a = ' + str(stiff_spa) + ' m' if has_stiff else 'Without transverse stiffeners'}",
             f"$k_v = {kv:.2f}$"),
            ('', '', ''),
            ('**Web Shear Coefficient Cv (G2.1):**', '', ''),
            ('Limit 1',
             f"$\\frac{{h}}{{t_w}} \\leq 1.10 \\sqrt{{\\frac{{k_v E}}{{F_y}}}}$",
             f"${h_tw:.2f} \\leq 1.10 \\sqrt{{\\frac{{{kv:.2f} \\times {E_STEEL}}}{{{Fy}}}}} = {1.10 * math.sqrt(kv * E_STEEL / Fy):.2f}$"),
            ('Cv Value',
             f"Based on web slenderness",
             f"$C_v = {Cv:.3f}$"),
            ('', '', ''),
            ('**Nominal Shear Strength (Eq. G2-1):**', '', ''),
            ('Nominal Shear',
             f"$V_n = 0.6 \\cdot F_y \\cdot A_w \\cdot C_v$",
             f"$V_n = 0.6 \\times {Fy} \\times {Aw:.0f} \\times {Cv:.3f} / 1000 = {Vn:.2f}$ kN"),
            ('', '', ''),
            ('**Allowable Shear (ASD):**', '', ''),
            ('Safety Factor',
             f"$\\Omega_v = 1.50$ (AISC G1)",
             ""),
            ('Allowable Shear',
             f"$V_a = \\frac{{V_n}}{{\\Omega_v}}$",
             f"$V_a = \\frac{{{Vn:.2f}}}{{1.50}} = {Vn/1.50:.2f}$ kN"),
            ('', '', ''),
            ('**Demand/Capacity Check:**', '', ''),
            ('Shear Ratio',
             f"$\\frac{{V_u}}{{V_a}} \\leq 1.0$",
             f"$\\frac{{{V_crane + V_self:.2f}}}{{{Vn/1.50:.2f}}} = {(V_crane + V_self)/(Vn/1.50):.3f}$ {'✓ OK' if (V_crane + V_self)/(Vn/1.50) <= 1.0 else '✗ NG'}"),
        ]
    })
    
    # ========== 7. LATERAL BENDING ==========
    # Top flange lateral bending
    Sy_top = sec.tf_top * sec.bf_top**2 / 6  # Approximate
    Zy_top = sec.tf_top * sec.bf_top**2 / 4  # Approximate
    Mn_y = Fy * Zy_top / 1e6
    Ma_y = Mn_y / 1.67
    
    ratio_lat = M_lat / Ma_y if Ma_y > 0 else 0
    
    calcs.append({
        'title': '7. LATERAL BENDING (Top Flange)',
        'ref': 'AISC Design Guide 7, Section 4.3',
        'content': [
            ('Purpose', 'Check top flange for lateral bending due to crane lateral thrust'),
        ],
        'calculations': [
            ('**Top Flange Section Properties:**', '', ''),
            ('Plastic Section Modulus (weak axis)',
             f"$Z_y = \\frac{{t_f \\cdot b_f^2}}{{4}}$",
             f"$Z_y = \\frac{{{sec.tf_top:.0f} \\times {sec.bf_top:.0f}^2}}{{4}} = {Zy_top:.0f}$ mm³"),
            ('', '', ''),
            ('**Lateral Moment:**', '', ''),
            ('Lateral Force per Wheel',
             f"From crane data",
             f"$H_{{wheel}} = {cranes[0].lateral_per_wheel():.2f}$ kN (per wheel)"),
            ('Lateral Moment',
             f"$M_{{lat}} = H_{{wheel}} \\cdot (h_{{rail}} + e)$",
             f"$M_{{lat}} = {M_lat:.2f}$ kN-m"),
            ('', '', ''),
            ('**Nominal Lateral Moment:**', '', ''),
            ('Nominal Moment',
             f"$M_{{n,y}} = F_y \\cdot Z_y$",
             f"$M_{{n,y}} = {Fy} \\times {Zy_top:.0f} / 10^6 = {Mn_y:.2f}$ kN-m"),
            ('Allowable Moment',
             f"$M_{{a,y}} = \\frac{{M_{{n,y}}}}{{\\Omega_b}}$",
             f"$M_{{a,y}} = \\frac{{{Mn_y:.2f}}}{{1.67}} = {Ma_y:.2f}$ kN-m"),
            ('', '', ''),
            ('**Demand/Capacity Check:**', '', ''),
            ('Lateral Ratio',
             f"$\\frac{{M_{{lat}}}}{{M_{{a,y}}}} \\leq 1.0$",
             f"$\\frac{{{M_lat:.2f}}}{{{Ma_y:.2f}}} = {ratio_lat:.3f}$ {'✓ OK' if ratio_lat <= 1.0 else '✗ NG'}"),
        ]
    })
    
    # ========== 8. COMBINED BIAXIAL BENDING ==========
    ratio_combined = ratio_flex + ratio_lat
    
    calcs.append({
        'title': '8. COMBINED BIAXIAL BENDING',
        'ref': 'AISC 360-16, Chapter H (H1)',
        'content': [
            ('Purpose', 'Check combined strong axis and weak axis bending'),
        ],
        'calculations': [
            ('**Interaction Equation (Eq. H1-1b):**', '', ''),
            ('For flexure only (no axial)',
             f"$\\frac{{M_{{ux}}}}{{M_{{ax}}}} + \\frac{{M_{{uy}}}}{{M_{{ay}}}} \\leq 1.0$",
             f"${ratio_flex:.3f} + {ratio_lat:.3f} = {ratio_combined:.3f}$ {'✓ OK' if ratio_combined <= 1.0 else '✗ NG'}"),
        ]
    })
    
    # ========== 9. DEFLECTION ==========
    dl = CRANE_CLASSES[crane_cls]['defl_limit']
    delta_allow = L * 1000 / dl
    defl_ratio = delta_actual / delta_allow if delta_allow > 0 else 0
    
    calcs.append({
        'title': '9. DEFLECTION CHECK',
        'ref': 'AISC Design Guide 7, Table 3.1; CMAA 70',
        'content': [
            ('Crane Class', f"{crane_cls}"),
            ('Deflection Limit', f"L/{dl}"),
        ],
        'calculations': [
            ('**Allowable Deflection:**', '', ''),
            ('Allowable',
             f"$\\delta_{{allow}} = \\frac{{L}}{{{dl}}}$",
             f"$\\delta_{{allow}} = \\frac{{{L*1000:.0f}}}{{{dl}}} = {delta_allow:.2f}$ mm"),
            ('', '', ''),
            ('**Actual Deflection (Influence Line Method):**', '', ''),
            ('Actual Deflection',
             f"$\\delta_{{actual}}$ (from moving crane loads)",
             f"$\\delta_{{actual}} = {delta_actual:.2f}$ mm"),
            ('', '', ''),
            ('**Demand/Capacity Check:**', '', ''),
            ('Deflection Ratio',
             f"$\\frac{{\\delta_{{actual}}}}{{\\delta_{{allow}}}} \\leq 1.0$",
             f"$\\frac{{{delta_actual:.2f}}}{{{delta_allow:.2f}}} = {defl_ratio:.3f}$ {'✓ OK' if defl_ratio <= 1.0 else '✗ NG'}"),
        ]
    })
    
    # ========== 10. WELD DESIGN (For Built-up Sections) ==========
    if sec.sec_type == 'built_up':
        wd = pg_results.get('weld_design', {})
        t_flange = min(sec.tf_top, sec.tf_bot)
        
        calcs.append({
            'title': '10. WELD DESIGN (Web-to-Flange)',
            'ref': 'AISC 360-16, Chapter J (J2)',
            'content': [
                ('Purpose', 'Design fillet welds connecting web to flanges'),
                ('Electrode', f"E70XX (FEXX = {wd.get('FEXX', 482)} MPa)"),
            ],
            'calculations': [
                ('**Minimum Weld Size (Table J2.4):**', '', ''),
                ('Thinner Part Joined',
                 f"$t_{{min}} = \\min(t_w, t_f) = \\min({sec.tw:.0f}, {t_flange:.0f})$",
                 f"$t_{{min}} = {min(sec.tw, t_flange):.0f}$ mm"),
                ('Minimum Weld Size',
                 f"From Table J2.4 based on $t_{{min}}$",
                 f"$w_{{min}} = {wd.get('w_min', 5):.0f}$ mm"),
                ('Provided Weld Size',
                 f"$w = {weld_size}$ mm",
                 f"$w = {weld_size}$ mm ≥ $w_{{min}} = {wd.get('w_min', 5):.0f}$ mm → **{wd.get('size_check', 'OK')}**"),
                ('', '', ''),
                ('**Maximum Weld Size (J2.2b):**', '', ''),
                ('Maximum Weld',
                 f"$w_{{max}} = t_{{thin}} - 2$ mm (for $t > 6$ mm)",
                 f"$w_{{max}} = {sec.tw:.0f} - 2 = {wd.get('w_max', sec.tw-2):.0f}$ mm"),
                ('', '', ''),
                ('**Effective Throat (J2.2a):**', '', ''),
                ('Throat Dimension',
                 f"$a = 0.707 \\times w$",
                 f"$a = 0.707 \\times {weld_size} = {wd.get('a_throat', 0.707*weld_size):.2f}$ mm"),
                ('', '', ''),
                ('**Shear Flow at Web-Flange Junction:**', '', ''),
                ('First Moment of Area',
                 f"$Q = A_f \\times \\bar{{y}}_f$",
                 f"$Q = {wd.get('Q', 0):.0f}$ mm³"),
                ('Shear Flow',
                 f"$q = \\frac{{V \\times Q}}{{I_x}}$",
                 f"$q = \\frac{{{V_crane + V_self:.1f} \\times 1000 \\times {wd.get('Q', 0):.0f}}}{{{sec.Ix:.2e}}} = {wd.get('q', 0):.2f}$ N/mm"),
                ('Shear per Weld (2 welds)',
                 f"$q_{{weld}} = \\frac{{q}}{{2}}$",
                 f"$q_{{weld}} = \\frac{{{wd.get('q', 0):.2f}}}{{2}} = {wd.get('q_per_weld', 0):.2f}$ N/mm"),
                ('', '', ''),
                ('**Weld Capacity (J2.4):**', '', ''),
                ('Nominal Strength',
                 f"$F_{{nw}} = 0.6 \\times F_{{EXX}}$",
                 f"$F_{{nw}} = 0.6 \\times {wd.get('FEXX', 482)} = {0.6 * wd.get('FEXX', 482):.0f}$ MPa"),
                ('Weld Capacity per mm',
                 f"$R_n = F_{{nw}} \\times a \\times 2$ (both sides)",
                 f"$R_n = {0.6 * wd.get('FEXX', 482):.0f} \\times {wd.get('a_throat', 0.707*weld_size):.2f} \\times 2 = {wd.get('Rn', 0):.1f}$ N/mm"),
                ('Allowable (Ω = 2.0)',
                 f"$R_a = \\frac{{R_n}}{{\\Omega}}$",
                 f"$R_a = \\frac{{{wd.get('Rn', 0):.1f}}}{{2.0}} = {wd.get('Ra', 0):.1f}$ N/mm"),
                ('', '', ''),
                ('**Demand/Capacity Check:**', '', ''),
                ('Weld Stress Ratio',
                 f"$\\frac{{q}}{{R_a}} \\leq 1.0$",
                 f"$\\frac{{{wd.get('q', 0):.2f}}}{{{wd.get('Ra', 1):.1f}}} = {wd.get('stress_ratio', 0):.3f}$ {'✓ OK' if wd.get('stress_ratio', 0) <= 1.0 else '✗ NG'}"),
            ]
        })
    
    # ========== 11. STIFFENER DESIGN ==========
    if has_stiff and stiff_spa > 0:
        st_req = pg_results.get('stiffener_requirements', {})
        shear_int = pg_results.get('shear_interior_panel', {})
        
        # Get stiffener dimensions from stiff_data if available
        a = stiff_spa * 1000  # mm
        a_h = a / sec.hw
        
        # Calculate stiffener moment of inertia (assuming pair of stiffeners)
        # Default values if not provided
        b_st = st_req.get('b_min', 100)  # stiffener width
        t_st = 10  # default thickness
        
        # Moment of inertia of stiffener pair about web centerline
        I_st = 2 * (t_st * b_st**3 / 12 + t_st * b_st * (b_st/2 + sec.tw/2)**2)
        
        calcs.append({
            'title': '11. TRANSVERSE STIFFENER DESIGN',
            'ref': 'AISC 360-16, Section G2.2',
            'content': [
                ('Purpose', 'Prevent web shear buckling and enable tension field action'),
                ('Stiffener Spacing', f"$a = {a:.0f}$ mm = {stiff_spa:.2f} m"),
            ],
            'calculations': [
                ('**Aspect Ratio:**', '', ''),
                ('Aspect Ratio',
                 f"$\\frac{{a}}{{h}} = \\frac{{{a:.0f}}}{{{sec.hw:.0f}}}$",
                 f"$\\frac{{a}}{{h}} = {a_h:.2f}$"),
                ('TFA Limit',
                 f"$\\frac{{a}}{{h}} \\leq 3.0$ and $\\frac{{a}}{{h}} \\leq \\left(\\frac{{260}}{{h/t_w}}\\right)^2$",
                 f"${a_h:.2f} \\leq 3.0$ → {'✓' if a_h <= 3.0 else '✗'}, ${a_h:.2f} \\leq {(260/(sec.hw/sec.tw))**2:.2f}$ → {'✓' if a_h <= (260/(sec.hw/sec.tw))**2 else '✗'}"),
                ('', '', ''),
                ('**Minimum Moment of Inertia (G2.2):**', '', ''),
                ('Factor j',
                 f"$j = \\frac{{2.5}}{{(a/h)^2}} - 2 \\geq 0.5$",
                 f"$j = \\frac{{2.5}}{{{a_h:.2f}^2}} - 2 = {max(2.5/a_h**2 - 2, 0.5):.2f}$"),
                ('Required I_st (Eq. G2-7)',
                 f"$I_{{st,min}} = j \\times h \\times t_w^3$",
                 f"$I_{{st,min}} = {st_req.get('j', 0.5):.2f} \\times {sec.hw:.0f} \\times {sec.tw:.0f}^3 = {st_req.get('Ist_min1', 0):.0f}$ mm⁴"),
                ('', '', ''),
                ('**Minimum Width (G2.2):**', '', ''),
                ('Minimum Stiffener Width',
                 f"$b_{{st,min}} = \\frac{{h}}{{30}} + t_w$",
                 f"$b_{{st,min}} = \\frac{{{sec.hw:.0f}}}{{30}} + {sec.tw:.0f} = {st_req.get('b_min', sec.hw/30 + sec.tw):.1f}$ mm"),
                ('', '', ''),
                ('**Stiffener Slenderness (Table B4.1a Case 4):**', '', ''),
                ('Slenderness Limit',
                 f"$\\frac{{b_{{st}}}}{{t_{{st}}}} \\leq 0.56 \\sqrt{{\\frac{{E}}{{F_y}}}}$",
                 f"$\\frac{{b_{{st}}}}{{t_{{st}}}} \\leq 0.56 \\sqrt{{\\frac{{{E_STEEL}}}{{{Fy}}}}} = {0.56 * math.sqrt(E_STEEL/Fy):.1f}$"),
                ('', '', ''),
                ('**Provided vs Required:**', '', ''),
                ('Provided I_st',
                 f"$I_{{st}} = 2 \\times \\frac{{t_{{st}} \\times b_{{st}}^3}}{{12}} + ...$",
                 f"$I_{{st,prov}} = {I_st:.0f}$ mm⁴"),
                ('Check',
                 f"$I_{{st,prov}} \\geq I_{{st,min}}$",
                 f"${I_st:.0f}$ ≥ ${st_req.get('Ist_min', 0):.0f}$ → {'✓ OK' if I_st >= st_req.get('Ist_min', 0) else '✗ NG'}"),
            ]
        })
        
        # Add Bearing Stiffener section if applicable
        calcs.append({
            'title': '11a. BEARING STIFFENER DESIGN (At Supports)',
            'ref': 'AISC 360-16, Section J10.8',
            'content': [
                ('Purpose', 'Transfer concentrated loads and prevent web yielding/crippling'),
            ],
            'calculations': [
                ('**Bearing Stiffener Requirements:**', '', ''),
                ('Required when',
                 f"$R_u > \\phi R_n$ (web yielding or crippling)",
                 f"Check web local yielding and crippling limits"),
                ('', '', ''),
                ('**Effective Column Area (J10.8):**', '', ''),
                ('Effective Length',
                 f"$25 t_w$ strip of web on each side",
                 f"$25 \\times {sec.tw:.0f} = {25*sec.tw:.0f}$ mm each side"),
                ('Total Width',
                 f"$L_{{eff}} = 2 \\times b_{{st}} + t_w + 2 \\times 25 t_w$",
                 f"Effective cross-section for column buckling"),
                ('', '', ''),
                ('**Column Buckling Check:**', '', ''),
                ('Slenderness',
                 f"$KL/r$ of stiffener as column",
                 f"$K = 0.75$ (fixed-pinned)"),
                ('Critical Stress',
                 f"$F_{{cr}}$ per Chapter E",
                 f"Use effective section properties"),
                ('', '', ''),
                ('**Design Strength:**', '', ''),
                ('Nominal Strength',
                 f"$P_n = F_{{cr}} \\times A_{{eff}}$",
                 f"Must exceed reaction $R_u$"),
            ]
        })
    
    # ========== 12. FATIGUE ==========
    fc = FATIGUE_CATS[fat_cat]
    cycles = CRANE_CLASSES[crane_cls]['max_cycles']
    
    # Calculate allowable stress range
    Fsr_calc = (fc['Cf'] / cycles) ** 0.333
    Fsr = max(Fsr_calc, fc['thresh'])  # Cannot be less than threshold
    
    # Calculate actual stress range (moment range / Sx)
    # For crane runway, M_range ≈ M_max (full load to no load cycle)
    M_range = M_crane  # kN-m
    f_sr = M_range * 1e6 / sec.Sx if sec.Sx > 0 else 0  # MPa
    
    # Fatigue ratio
    fatigue_ratio = f_sr / Fsr if Fsr > 0 else 999
    fatigue_status = 'OK' if fatigue_ratio <= 1.0 else 'NG'
    
    calcs.append({
        'title': '12. FATIGUE CHECK',
        'ref': 'AISC 360-16, Appendix 3; Design Guide 7',
        'content': [
            ('Fatigue Category', f"{fat_cat} - {fc.get('desc', 'Welded connection')}"),
            ('Design Cycles', f"N = {cycles:,}"),
        ],
        'calculations': [
            ('**Fatigue Parameters (Table A-3.1):**', '', ''),
            ('Fatigue Constant',
             f"$C_f$ for Category {fat_cat}",
             f"$C_f = {fc['Cf']:.2e}$"),
            ('Threshold Stress',
             f"$F_{{TH}}$",
             f"$F_{{TH}} = {fc['thresh']}$ MPa"),
            ('', '', ''),
            ('**Allowable Stress Range (Eq. A-3-1):**', '', ''),
            ('Calculated FSR',
             f"$F_{{SR,calc}} = \\left( \\frac{{C_f}}{{n}} \\right)^{{0.333}}$",
             f"$F_{{SR,calc}} = \\left( \\frac{{{fc['Cf']:.2e}}}{{{cycles}}} \\right)^{{0.333}} = {Fsr_calc:.2f}$ MPa"),
            ('Allowable FSR',
             f"$F_{{SR}} = \\max(F_{{SR,calc}}, F_{{TH}})$",
             f"$F_{{SR}} = \\max({Fsr_calc:.2f}, {fc['thresh']}) = {Fsr:.2f}$ MPa"),
            ('', '', ''),
            ('**Actual Stress Range:**', '', ''),
            ('Moment Range',
             f"$M_{{range}} = M_{{max}} - M_{{min}}$",
             f"$M_{{range}} = {M_range:.2f} - 0 = {M_range:.2f}$ kN-m (full cycle)"),
            ('Actual Stress Range',
             f"$f_{{sr}} = \\frac{{M_{{range}}}}{{S_x}}$",
             f"$f_{{sr}} = \\frac{{{M_range:.2f} \\times 10^6}}{{{sec.Sx:.0f}}} = {f_sr:.2f}$ MPa"),
            ('', '', ''),
            ('**Demand/Capacity Check:**', '', ''),
            ('Fatigue Ratio',
             f"$\\frac{{f_{{sr}}}}{{F_{{SR}}}} \\leq 1.0$",
             f"$\\frac{{{f_sr:.2f}}}{{{Fsr:.2f}}} = {fatigue_ratio:.3f}$ {'✓ OK' if fatigue_ratio <= 1.0 else '✗ NG'}"),
        ]
    })
    
    # ========== 13. SUMMARY ==========
    # Get weld ratio if available
    wd = pg_results.get('weld_design', {})
    weld_ratio = wd.get('stress_ratio', 0)
    weld_status = 'OK' if weld_ratio <= 1.0 else 'NG'
    
    # Build summary with all checks
    summary_calcs = [
        ('**Design Check Results:**', '', ''),
        ('Flexure',
         f"$M_u / M_a = {ratio_flex:.3f}$",
         f"{'✓ OK' if ratio_flex <= 1.0 else '✗ NG'}"),
        ('Lateral Bending',
         f"$M_{{lat}} / M_{{a,y}} = {ratio_lat:.3f}$",
         f"{'✓ OK' if ratio_lat <= 1.0 else '✗ NG'}"),
        ('Combined Biaxial',
         f"${ratio_flex:.3f} + {ratio_lat:.3f} = {ratio_combined:.3f}$",
         f"{'✓ OK' if ratio_combined <= 1.0 else '✗ NG'}"),
        ('Shear',
         f"$V_u / V_a = {ratios.get('Shear', 0):.3f}$",
         f"{'✓ OK' if ratios.get('Shear', 0) <= 1.0 else '✗ NG'}"),
        ('Web Local Yielding',
         f"Ratio = {ratios.get('WebYld', 0):.3f}",
         f"{'✓ OK' if ratios.get('WebYld', 0) <= 1.0 else '✗ NG'}"),
        ('Web Crippling',
         f"Ratio = {ratios.get('WebCrp', 0):.3f}",
         f"{'✓ OK' if ratios.get('WebCrp', 0) <= 1.0 else '✗ NG'}"),
        ('Deflection',
         f"$\\delta_{{act}} / \\delta_{{allow}} = {ratios.get('Defl', 0):.3f}$",
         f"{'✓ OK' if ratios.get('Defl', 0) <= 1.0 else '✗ NG'}"),
        ('Fatigue',
         f"$f_{{sr}} / F_{{SR}} = {fatigue_ratio:.3f}$",
         f"{'✓ OK' if fatigue_ratio <= 1.0 else '✗ NG'}"),
    ]
    
    # Add weld check for built-up sections
    if sec.sec_type == 'built_up':
        summary_calcs.append(
            ('Weld (Web-to-Flange)',
             f"$q / R_a = {weld_ratio:.3f}$",
             f"{'✓ OK' if weld_ratio <= 1.0 else '✗ NG'}")
        )
    
    # Determine governing check
    all_ratios = {
        'Flexure': ratio_flex,
        'Lateral': ratio_lat,
        'Combined': ratio_combined,
        'Shear': ratios.get('Shear', 0),
        'WebYld': ratios.get('WebYld', 0),
        'WebCrp': ratios.get('WebCrp', 0),
        'Deflection': ratios.get('Defl', 0),
        'Fatigue': fatigue_ratio,
    }
    if sec.sec_type == 'built_up':
        all_ratios['Weld'] = weld_ratio
    
    max_ratio = max(all_ratios.values())
    gov_check = max(all_ratios, key=all_ratios.get)
    overall_status = 'PASS' if max_ratio <= 1.0 else 'FAIL'
    
    summary_calcs.extend([
        ('', '', ''),
        ('**Governing Check:**', '', ''),
        ('Maximum Ratio',
         f"**{gov_check}**",
         f"**{max_ratio:.3f}**"),
        ('', '', ''),
        ('**Overall Status:**', '', ''),
        ('Design Status',
         f"All ratios ≤ 1.0 ?" if overall_status == 'PASS' else f"Max ratio = {max_ratio:.3f} > 1.0",
         f"**{'✓ PASS - Section is Adequate' if overall_status == 'PASS' else '✗ FAIL - Section is Inadequate'}**"),
    ])
    
    calcs.append({
        'title': '13. DESIGN SUMMARY',
        'ref': '',
        'content': [],
        'calculations': summary_calcs
    })
    
    return calcs


def generate_pdf_report(sec, Fy, Fu, cmp, gov, L, crane_cls, fat_cat, Lb, has_stiff, stiff_spa,
                        cranes, w_self, R_self, M_self, V_self, M_lat, ratios, 
                        weld_size=6, delta_actual=0, project_info=None):
    """
    Generate professional PDF report with detailed calculations.
    Returns bytes of the PDF file.
    """
    if not PDF_AVAILABLE:
        return None
    
    buffer = io.BytesIO()
    
    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=20*mm
    )
    
    # Define custom styles
    styles = getSampleStyleSheet()
    
    # Title style
    styles.add(ParagraphStyle(
        name='MainTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=HexColor('#1a5276'),
        spaceAfter=6*mm,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))
    
    # Section header style
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading1'],
        fontSize=12,
        textColor=HexColor('#1a5276'),
        spaceBefore=8*mm,
        spaceAfter=3*mm,
        fontName='Helvetica-Bold',
        borderColor=HexColor('#1a5276'),
        borderWidth=0,
        borderPadding=0
    ))
    
    # Subsection style
    styles.add(ParagraphStyle(
        name='SubSection',
        parent=styles['Heading2'],
        fontSize=10,
        textColor=HexColor('#2874a6'),
        spaceBefore=4*mm,
        spaceAfter=2*mm,
        fontName='Helvetica-Bold'
    ))
    
    # Normal text
    styles.add(ParagraphStyle(
        name='NormalText',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=2*mm,
        fontName='Helvetica'
    ))
    
    # Equation style
    styles.add(ParagraphStyle(
        name='Equation',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=10*mm,
        spaceAfter=1.5*mm,
        fontName='Helvetica-Oblique',
        textColor=HexColor('#333333')
    ))
    
    # Result style
    styles.add(ParagraphStyle(
        name='Result',
        parent=styles['Normal'],
        fontSize=9,
        leftIndent=10*mm,
        spaceAfter=2*mm,
        fontName='Helvetica-Bold',
        textColor=HexColor('#196f3d')
    ))
    
    # Code reference style
    styles.add(ParagraphStyle(
        name='CodeRef',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#7f8c8d'),
        fontName='Helvetica-Oblique',
        alignment=TA_RIGHT
    ))
    
    # Build story (content)
    story = []
    
    # ==================== COVER PAGE ====================
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("CRANE RUNWAY BEAM", styles['MainTitle']))
    story.append(Paragraph("DESIGN CALCULATIONS", styles['MainTitle']))
    story.append(Spacer(1, 10*mm))
    
    # Horizontal line
    story.append(HRFlowable(width="80%", thickness=2, color=HexColor('#1a5276'), 
                           spaceBefore=5*mm, spaceAfter=5*mm, hAlign='CENTER'))
    
    story.append(Paragraph("Per AISC 360-16 (ASD Method)", styles['NormalText']))
    story.append(Paragraph("AISC Design Guide 7 &amp; CMAA 70 Specifications", styles['NormalText']))
    
    story.append(Spacer(1, 15*mm))
    
    # Project info table
    proj = project_info or {}
    proj_data = [
        ['Project:', proj.get('project', 'Crane Runway Beam Design')],
        ['Designer:', proj.get('designer', '—')],
        ['Date:', datetime.now().strftime('%Y-%m-%d')],
        ['Section:', sec.name],
        ['Span:', f'{L/1000:.2f} m'],
        ['Service Class:', crane_cls],
    ]
    
    proj_table = Table(proj_data, colWidths=[40*mm, 80*mm])
    proj_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#1a5276')),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(proj_table)
    
    story.append(Spacer(1, 20*mm))
    
    # Design Status Box
    overall_pass = all(r <= 1.0 for r in ratios.values() if isinstance(r, (int, float)))
    status_color = HexColor('#196f3d') if overall_pass else HexColor('#c0392b')
    status_text = "✓ DESIGN ADEQUATE" if overall_pass else "✗ DESIGN INADEQUATE"
    
    status_data = [[status_text]]
    status_table = Table(status_data, colWidths=[80*mm])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), status_color),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
    ]))
    story.append(status_table)
    
    story.append(PageBreak())
    
    # ==================== DESIGN SUMMARY ====================
    story.append(Paragraph("DESIGN SUMMARY", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#1a5276'), 
                           spaceBefore=1*mm, spaceAfter=3*mm))
    
    # Summary table
    summary_data = [
        ['Check', 'Demand', 'Capacity', 'Ratio', 'Status']
    ]
    
    check_items = [
        ('Flexure', 'flex'),
        ('Lateral Moment', 'lat'),
        ('Combined Biaxial', 'biax'),
        ('Shear', 'shear'),
        ('Web Yielding', 'wly'),
        ('Web Crippling', 'wcr'),
        ('Deflection', 'defl'),
        ('Fatigue', 'fatigue'),
    ]
    
    for name, key in check_items:
        ratio = ratios.get(key, 0)
        if ratio > 0:
            status = '✓ OK' if ratio <= 1.0 else '✗ NG'
            summary_data.append([name, '—', '—', f'{ratio:.3f}', status])
    
    summary_table = Table(summary_data, colWidths=[35*mm, 30*mm, 30*mm, 20*mm, 20*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#bdc3c7')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 5*mm))
    
    # Governing ratio
    max_ratio = max((v for v in ratios.values() if isinstance(v, (int, float))), default=0)
    gov_check = max((k for k, v in ratios.items() if v == max_ratio), default='—')
    story.append(Paragraph(f"<b>Governing Check:</b> {gov_check.upper()} with ratio = {max_ratio:.3f}", 
                          styles['NormalText']))
    
    story.append(PageBreak())
    
    # ==================== DETAILED CALCULATIONS ====================
    story.append(Paragraph("DETAILED CALCULATIONS", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#1a5276'), 
                           spaceBefore=1*mm, spaceAfter=3*mm))
    
    # Get detailed calculations
    calcs = gen_detailed_calcs(sec, Fy, Fu, cmp, gov, L, crane_cls, fat_cat, Lb, has_stiff, stiff_spa,
                               cranes, w_self, R_self, M_self, V_self, M_lat, ratios, weld_size, delta_actual)
    
    # Process each section
    for calc_section in calcs:
        # Section title
        story.append(Paragraph(calc_section['title'], styles['SubSection']))
        
        # Code reference
        if calc_section.get('ref'):
            story.append(Paragraph(f"Reference: {calc_section['ref']}", styles['CodeRef']))
        
        # Content items
        for item in calc_section.get('content', []):
            if isinstance(item, tuple) and len(item) >= 2:
                label, value = item[0], item[1]
                # Convert LaTeX-style notation to readable format
                value = convert_latex_to_text(value)
                story.append(Paragraph(f"<b>{label}:</b> {value}", styles['NormalText']))
        
        # Calculations
        for calc in calc_section.get('calculations', []):
            if isinstance(calc, tuple):
                if len(calc) >= 3:
                    desc, formula, result = calc[0], calc[1], calc[2]
                    # Convert LaTeX to readable text
                    formula = convert_latex_to_text(formula)
                    result = convert_latex_to_text(result)
                    
                    if desc:
                        story.append(Paragraph(f"<b>{desc}</b>", styles['NormalText']))
                    if formula and formula != result:
                        story.append(Paragraph(f"  {formula}", styles['Equation']))
                    if result:
                        story.append(Paragraph(f"  → {result}", styles['Result']))
                elif len(calc) == 2:
                    desc, value = calc[0], calc[1]
                    value = convert_latex_to_text(value)
                    story.append(Paragraph(f"<b>{desc}:</b> {value}", styles['NormalText']))
        
        story.append(Spacer(1, 3*mm))
    
    # ==================== FOOTER INFO ====================
    story.append(PageBreak())
    story.append(Paragraph("NOTES &amp; REFERENCES", styles['SectionHeader']))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#1a5276'), 
                           spaceBefore=1*mm, spaceAfter=3*mm))
    
    notes = [
        "1. Design per AISC 360-16 Specification for Structural Steel Buildings (ASD Method)",
        "2. Crane loads per CMAA 70 Specifications for Top Running Bridge &amp; Gantry Type Multiple Girder Electric Overhead Traveling Cranes",
        "3. Runway beam design per AISC Design Guide 7: Industrial Buildings - Roofs to Anchor Rods",
        "4. Safety factors: Ω = 1.67 for flexure, Ω = 1.50 for shear",
        "5. Fatigue design per AISC 360-16 Appendix 3",
        f"6. Service Class {crane_cls} with fatigue category {fat_cat}",
        "7. Impact factors applied per CMAA 70 recommendations",
        "8. Lateral loads include thrust (20% of lifted load) and side pull forces",
    ]
    
    for note in notes:
        story.append(Paragraph(note, styles['NormalText']))
    
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(f"<i>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>", 
                          styles['CodeRef']))
    
    # Build PDF
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()


def convert_latex_to_text(text):
    """Convert LaTeX-style math notation to readable text for PDF"""
    if not text:
        return ""
    
    # Convert common LaTeX patterns
    replacements = [
        (r'$', ''),
        (r'\times', '×'),
        (r'\cdot', '·'),
        (r'\sqrt', '√'),
        (r'\frac{', '('),
        (r'}{', ')/('),
        (r'\sum', 'Σ'),
        (r'\Delta', 'Δ'),
        (r'\delta', 'δ'),
        (r'\sigma', 'σ'),
        (r'\tau', 'τ'),
        (r'\phi', 'φ'),
        (r'\Phi', 'Φ'),
        (r'\lambda', 'λ'),
        (r'\Lambda', 'Λ'),
        (r'\omega', 'ω'),
        (r'\Omega', 'Ω'),
        (r'\pi', 'π'),
        (r'\leq', '≤'),
        (r'\geq', '≥'),
        (r'\neq', '≠'),
        (r'\approx', '≈'),
        (r'\infty', '∞'),
        (r'\\', ' '),
        (r'_{', '_'),
        (r'^{', '^'),
        (r'{', ''),
        (r'}', ''),
        (r'**', ''),
        (r'✓', '✓'),
        (r'✗', '✗'),
    ]
    
    result = str(text)
    for old, new in replacements:
        result = result.replace(old, new)
    
    # Clean up subscripts and superscripts
    import re
    result = re.sub(r'_([a-zA-Z0-9,]+)', r'_\1', result)
    result = re.sub(r'\^([a-zA-Z0-9,]+)', r'^(\1)', result)
    
    return result


def gen_calcs(sec, Fy, Fu, cmp, gov, L, crane_cls, fat_cat, Lb, has_stiff, stiff_spa):
    """Legacy text-based calculation summary (kept for backwards compatibility)"""
    c = []
    c.append("="*70)
    c.append("DETAILED DESIGN CALCULATIONS - RUNWAY BEAM")
    c.append("Per AISC 360-16 (ASD), Design Guide 7, CMAA 70")
    c.append("="*70 + "\n")
    c.append("1. SECTION PROPERTIES")
    c.append("-"*50)
    c.append(f"Section: {sec.name}")
    c.append(f"d = {sec.d:.0f} mm, hw = {sec.hw:.0f} mm, tw = {sec.tw:.0f} mm")
    c.append(f"Top Flange: {sec.bf_top:.0f} x {sec.tf_top:.0f} mm")
    c.append(f"Bot Flange: {sec.bf_bot:.0f} x {sec.tf_bot:.0f} mm")
    c.append(f"A = {sec.A:.0f} mm2, Ix = {sec.Ix/1e6:.2f}E6 mm4")
    c.append(f"Sx = {sec.Sx/1e3:.1f}E3 mm3, Zx = {sec.Zx/1e3:.1f}E3 mm3")
    c.append(f"rx = {sec.rx:.1f} mm, ry = {sec.ry:.1f} mm")
    c.append(f"Weight = {sec.mass:.1f} kg/m\n")
    
    c.append("2. MATERIAL: Fy = {} MPa, Fu = {} MPa\n".format(Fy, Fu))
    
    c.append("3. COMPACTNESS (Table B4.1b)")
    c.append(f"Flange: lf = {cmp['lf']:.2f}, lpf = {cmp['lpf']:.2f} -> {cmp['flg']}")
    c.append(f"Web: lw = {cmp['lw']:.2f}, lpw = {cmp['lpw']:.2f} -> {cmp['web']}\n")
    
    if gov:
        mc = gov.get('moment')
        if mc:
            c.append("4. LOADS: {} | M = {:.2f} kN-m @ {:.2f}m\n".format(mc.desc, mc.M_max, mc.M_pos))
    
    Lp, Lr = calc_Lp_Lr(sec, Fy)
    Mp = Fy * sec.Zx / 1e6
    Mn, _, _, ltb = calc_Mn(sec, Fy, Lb, cmp)
    
    if sec.rts > 0 and sec.Sx > 0 and sec.ho > 0:
        Fcr = math.pi**2 * E_STEEL / (Lb/sec.rts)**2 * math.sqrt(1 + 0.078*sec.J/(sec.Sx*sec.ho)*(Lb/sec.rts)**2)
    else:
        Fcr = 0.7 * Fy
    Mn_elastic = Fcr * sec.Sx / 1e6
    
    c.append("5. FLEXURE (Chapter F)")
    c.append(f"Lp = {Lp/1000:.2f} m, Lr = {Lr/1000:.2f} m, Lb = {Lb/1000:.2f} m")
    c.append(f"Mp = Fy*Zx = {Fy}*{sec.Zx/1e3:.1f}E3 / 1E6 = {Mp:.2f} kN-m")
    c.append(f"Fcr = {Fcr:.2f} MPa, Fcr*Sx = {Mn_elastic:.2f} kN-m")
    c.append(f"LTB: {ltb}, Mn = min(Fcr*Sx, Mp) = {Mn:.2f} kN-m")
    c.append(f"Allowable = Mn/1.67 = {Mn/1.67:.2f} kN-m\n")
    
    Vn, Cv = calc_Vn(sec, Fy, has_stiff, stiff_spa)
    c.append("6. SHEAR (Chapter G)")
    c.append(f"Cv = {Cv:.3f}, Vn = {Vn:.2f} kN")
    c.append(f"Allowable = Vn/1.50 = {Vn/1.5:.2f} kN\n")
    
    dl = CRANE_CLASSES[crane_cls]['defl_limit']
    c.append("7. DEFLECTION: L/{} = {:.2f} mm\n".format(dl, L*1000/dl))
    
    fc = FATIGUE_CATS[fat_cat]
    cycles = CRANE_CLASSES[crane_cls]['max_cycles']
    c.append("8. FATIGUE (Appendix 3)")
    c.append(f"Category {fat_cat}, N = {cycles:,.0f}")
    c.append(f"Threshold = {fc['thresh']} MPa\n")
    
    c.append("9. CODES: AISC 360-16, DG7, CMAA 70")
    return "\n".join(c)


def draw_section(sec):
    """Draw a professional section sketch with all dimensions labeled"""
    fig = go.Figure()
    
    # Scale factor for better visualization
    d = sec.d
    bf_top = sec.bf_top
    tf_top = sec.tf_top
    bf_bot = sec.bf_bot
    tf_bot = sec.tf_bot
    tw = sec.tw
    hw = sec.hw
    
    # Colors
    steel_color = 'rgb(180, 180, 180)'
    steel_line = 'rgb(80, 80, 80)'
    dim_color = 'rgb(0, 0, 0)'
    
    # Draw I-section shape
    # Bottom flange
    fig.add_shape(type="rect", 
                  x0=-bf_bot/2, y0=0, x1=bf_bot/2, y1=tf_bot,
                  line=dict(color=steel_line, width=2), 
                  fillcolor=steel_color)
    
    # Web
    fig.add_shape(type="rect", 
                  x0=-tw/2, y0=tf_bot, x1=tw/2, y1=tf_bot+hw,
                  line=dict(color=steel_line, width=2), 
                  fillcolor=steel_color)
    
    # Top flange
    fig.add_shape(type="rect", 
                  x0=-bf_top/2, y0=d-tf_top, x1=bf_top/2, y1=d,
                  line=dict(color=steel_line, width=2), 
                  fillcolor=steel_color)
    
    # Cap channel if present
    cap_height = 0
    if sec.has_cap and sec.cap_d > 0:
        cap_height = sec.cap_d * 0.4  # Visual height for channel
        # Channel web (horizontal on top)
        fig.add_shape(type="rect",
                      x0=-sec.cap_d/2, y0=d, x1=sec.cap_d/2, y1=d + 8,
                      line=dict(color=steel_line, width=2),
                      fillcolor='rgb(160, 160, 180)')
        # Channel flanges (pointing up)
        fig.add_shape(type="rect",
                      x0=-sec.cap_d/2, y0=d, x1=-sec.cap_d/2 + 10, y1=d + cap_height,
                      line=dict(color=steel_line, width=2),
                      fillcolor='rgb(160, 160, 180)')
        fig.add_shape(type="rect",
                      x0=sec.cap_d/2 - 10, y0=d, x1=sec.cap_d/2, y1=d + cap_height,
                      line=dict(color=steel_line, width=2),
                      fillcolor='rgb(160, 160, 180)')
    
    # Dimension line offset
    max_bf = max(bf_top, bf_bot)
    offset = max_bf * 0.15
    
    # === DIMENSION LINES ===
    
    # --- Total depth D (right side) ---
    x_d = max_bf/2 + offset * 2
    # Vertical line
    fig.add_shape(type="line", x0=x_d, y0=0, x1=x_d, y1=d,
                  line=dict(color=dim_color, width=1))
    # Top tick
    fig.add_shape(type="line", x0=x_d-5, y0=d, x1=x_d+5, y1=d,
                  line=dict(color=dim_color, width=1))
    # Bottom tick
    fig.add_shape(type="line", x0=x_d-5, y0=0, x1=x_d+5, y1=0,
                  line=dict(color=dim_color, width=1))
    # Extension lines
    fig.add_shape(type="line", x0=max_bf/2, y0=0, x1=x_d+5, y1=0,
                  line=dict(color=dim_color, width=0.5, dash='dot'))
    fig.add_shape(type="line", x0=max_bf/2, y0=d, x1=x_d+5, y1=d,
                  line=dict(color=dim_color, width=0.5, dash='dot'))
    # Label
    fig.add_annotation(x=x_d + offset, y=d/2, text=f"d={d:.0f}",
                      showarrow=False, font=dict(size=11, color=dim_color),
                      textangle=-90)
    
    # --- Web height hw (right side, inner) ---
    x_hw = max_bf/2 + offset * 0.8
    fig.add_shape(type="line", x0=x_hw, y0=tf_bot, x1=x_hw, y1=tf_bot+hw,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=x_hw-4, y0=tf_bot, x1=x_hw+4, y1=tf_bot,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=x_hw-4, y0=tf_bot+hw, x1=x_hw+4, y1=tf_bot+hw,
                  line=dict(color=dim_color, width=1))
    fig.add_annotation(x=x_hw + offset*0.6, y=tf_bot + hw/2, text=f"hw={hw:.0f}",
                      showarrow=False, font=dict(size=10, color=dim_color),
                      textangle=-90)
    
    # --- Top flange thickness tf_top (right side) ---
    x_tf = bf_top/2 + offset * 0.5
    fig.add_shape(type="line", x0=x_tf, y0=d-tf_top, x1=x_tf, y1=d,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=x_tf-3, y0=d-tf_top, x1=x_tf+3, y1=d-tf_top,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=x_tf-3, y0=d, x1=x_tf+3, y1=d,
                  line=dict(color=dim_color, width=1))
    fig.add_annotation(x=x_tf + offset*0.8, y=d-tf_top/2, text=f"tf={tf_top:.0f}",
                      showarrow=False, font=dict(size=9, color=dim_color))
    
    # --- Bottom flange thickness tf_bot (right side) ---
    x_tfb = bf_bot/2 + offset * 0.5
    fig.add_shape(type="line", x0=x_tfb, y0=0, x1=x_tfb, y1=tf_bot,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=x_tfb-3, y0=0, x1=x_tfb+3, y1=0,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=x_tfb-3, y0=tf_bot, x1=x_tfb+3, y1=tf_bot,
                  line=dict(color=dim_color, width=1))
    fig.add_annotation(x=x_tfb + offset*0.8, y=tf_bot/2, text=f"tf={tf_bot:.0f}",
                      showarrow=False, font=dict(size=9, color=dim_color))
    
    # --- Top flange width bf_top (top) ---
    y_bf_top = d + offset * 0.5
    fig.add_shape(type="line", x0=-bf_top/2, y0=y_bf_top, x1=bf_top/2, y1=y_bf_top,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=-bf_top/2, y0=y_bf_top-5, x1=-bf_top/2, y1=y_bf_top+5,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=bf_top/2, y0=y_bf_top-5, x1=bf_top/2, y1=y_bf_top+5,
                  line=dict(color=dim_color, width=1))
    # Extension lines
    fig.add_shape(type="line", x0=-bf_top/2, y0=d, x1=-bf_top/2, y1=y_bf_top+5,
                  line=dict(color=dim_color, width=0.5, dash='dot'))
    fig.add_shape(type="line", x0=bf_top/2, y0=d, x1=bf_top/2, y1=y_bf_top+5,
                  line=dict(color=dim_color, width=0.5, dash='dot'))
    fig.add_annotation(x=0, y=y_bf_top + offset*0.4, text=f"bf_top={bf_top:.0f}",
                      showarrow=False, font=dict(size=10, color=dim_color))
    
    # --- Bottom flange width bf_bot (bottom) ---
    y_bf_bot = -offset * 0.5
    fig.add_shape(type="line", x0=-bf_bot/2, y0=y_bf_bot, x1=bf_bot/2, y1=y_bf_bot,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=-bf_bot/2, y0=y_bf_bot-5, x1=-bf_bot/2, y1=y_bf_bot+5,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=bf_bot/2, y0=y_bf_bot-5, x1=bf_bot/2, y1=y_bf_bot+5,
                  line=dict(color=dim_color, width=1))
    # Extension lines
    fig.add_shape(type="line", x0=-bf_bot/2, y0=0, x1=-bf_bot/2, y1=y_bf_bot-5,
                  line=dict(color=dim_color, width=0.5, dash='dot'))
    fig.add_shape(type="line", x0=bf_bot/2, y0=0, x1=bf_bot/2, y1=y_bf_bot-5,
                  line=dict(color=dim_color, width=0.5, dash='dot'))
    fig.add_annotation(x=0, y=y_bf_bot - offset*0.4, text=f"bf_bot={bf_bot:.0f}",
                      showarrow=False, font=dict(size=10, color=dim_color))
    
    # --- Web thickness tw (left side, at mid-height) ---
    y_tw = tf_bot + hw/2
    x_tw_left = -max_bf/2 - offset * 0.3
    # Horizontal line showing tw
    fig.add_shape(type="line", x0=-tw/2, y0=y_tw, x1=tw/2, y1=y_tw,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=-tw/2, y0=y_tw-5, x1=-tw/2, y1=y_tw+5,
                  line=dict(color=dim_color, width=1))
    fig.add_shape(type="line", x0=tw/2, y0=y_tw-5, x1=tw/2, y1=y_tw+5,
                  line=dict(color=dim_color, width=1))
    fig.add_annotation(x=0, y=y_tw + 15, text=f"tw={tw:.0f}",
                      showarrow=False, font=dict(size=9, color=dim_color))
    
    # --- Centroid line (dashed red) ---
    fig.add_shape(type="line", 
                  x0=-max_bf/2 - offset, y0=sec.y_bar, 
                  x1=max_bf/2 + offset, y1=sec.y_bar,
                  line=dict(color='red', width=1.5, dash='dash'))
    fig.add_annotation(x=-max_bf/2 - offset*1.5, y=sec.y_bar, 
                      text=f"ȳ={sec.y_bar:.0f}",
                      showarrow=False, font=dict(size=9, color='red'))
    
    # Cap channel dimension if present
    if sec.has_cap and sec.cap_d > 0:
        y_cap = d + cap_height + offset * 0.3
        fig.add_shape(type="line", x0=-sec.cap_d/2, y0=y_cap, x1=sec.cap_d/2, y1=y_cap,
                      line=dict(color=dim_color, width=1))
        fig.add_shape(type="line", x0=-sec.cap_d/2, y0=y_cap-5, x1=-sec.cap_d/2, y1=y_cap+5,
                      line=dict(color=dim_color, width=1))
        fig.add_shape(type="line", x0=sec.cap_d/2, y0=y_cap-5, x1=sec.cap_d/2, y1=y_cap+5,
                      line=dict(color=dim_color, width=1))
        fig.add_annotation(x=0, y=y_cap + 10, text=f"Cap: {sec.cap_name}",
                          showarrow=False, font=dict(size=9, color='blue'))
    
    # Update layout
    margin_x = max_bf * 0.4
    margin_y = d * 0.15
    
    fig.update_layout(
        title=dict(text="Section Dimensions (mm)", font=dict(size=14)),
        height=450,
        xaxis=dict(
            scaleanchor="y", 
            scaleratio=1, 
            showgrid=False, 
            zeroline=False, 
            showticklabels=False,
            range=[-max_bf/2 - margin_x, max_bf/2 + margin_x * 1.5]
        ),
        yaxis=dict(
            showgrid=False, 
            zeroline=False, 
            showticklabels=False,
            range=[-margin_y, d + cap_height + margin_y]
        ),
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='white'
    )
    
    return fig


def draw_beam(case, L):
    fig = make_subplots(rows=3, cols=1, subplot_titles=('Loading Arrangement', 'Moment Diagram (kN-m)', 'Shear Diagram (kN)'), 
                        vertical_spacing=0.12, row_heights=[0.30, 0.35, 0.35])
    
    # Beam line
    fig.add_trace(go.Scatter(x=[0, L], y=[0, 0], mode='lines', line=dict(color='black', width=6), 
                             name='Beam', showlegend=False), row=1, col=1)
    
    # Supports (triangles)
    fig.add_trace(go.Scatter(x=[0], y=[-0.15], mode='markers', 
                             marker=dict(symbol='triangle-up', size=20, color='gray'),
                             name='Support', showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=[L], y=[-0.15], mode='markers', 
                             marker=dict(symbol='triangle-up', size=20, color='gray'),
                             showlegend=False), row=1, col=1)
    
    # Color scheme for different cranes
    crane_colors = {1: '#E74C3C', 2: '#3498DB', 3: '#27AE60'}
    crane_names = {1: 'Crane 1', 2: 'Crane 2', 3: 'Crane 3'}
    
    # Group wheels by crane
    cranes_in_case = {}
    for w in case.wheels:
        if w.crane_id not in cranes_in_case:
            cranes_in_case[w.crane_id] = []
        cranes_in_case[w.crane_id].append(w)
    
    # Draw wheels for each crane
    for crane_id, wheels in cranes_in_case.items():
        color = crane_colors.get(crane_id, '#E74C3C')
        wheels_sorted = sorted(wheels, key=lambda w: w.pos)
        
        # Draw wheel loads as arrows
        for w in wheels_sorted:
            # Arrow line
            fig.add_trace(go.Scatter(x=[w.pos, w.pos], y=[0.6, 0.05], mode='lines',
                                     line=dict(color=color, width=3),
                                     showlegend=False), row=1, col=1)
            # Arrow head
            fig.add_trace(go.Scatter(x=[w.pos], y=[0.05], mode='markers',
                                     marker=dict(symbol='triangle-down', size=12, color=color),
                                     showlegend=False), row=1, col=1)
            # Load value
            fig.add_annotation(x=w.pos, y=0.72, text=f"{w.Pv:.0f}kN",
                              showarrow=False, font=dict(size=9, color=color), row=1, col=1)
        
        # Draw crane bridge representation (connecting line between wheels)
        if len(wheels_sorted) >= 2:
            x_positions = [w.pos for w in wheels_sorted]
            fig.add_trace(go.Scatter(x=[min(x_positions), max(x_positions)], y=[0.45, 0.45],
                                     mode='lines', line=dict(color=color, width=8),
                                     name=f"Crane {crane_id}", showlegend=True), row=1, col=1)
            # Crane label
            mid_x = (min(x_positions) + max(x_positions)) / 2
            fig.add_annotation(x=mid_x, y=0.52, text=f"C{crane_id}",
                              showarrow=False, font=dict(size=11, color=color, weight='bold'), row=1, col=1)
        
        # Draw wheel circles at beam level
        for w in wheels_sorted:
            fig.add_trace(go.Scatter(x=[w.pos], y=[0], mode='markers',
                                     marker=dict(symbol='circle', size=14, color=color, 
                                                line=dict(color='black', width=1)),
                                     showlegend=False), row=1, col=1)
    
    # Reaction annotations
    fig.add_annotation(x=0, y=-0.35, text=f"R_L={case.R_left:.1f}kN",
                      showarrow=False, font=dict(size=10), row=1, col=1)
    fig.add_annotation(x=L, y=-0.35, text=f"R_R={case.R_right:.1f}kN",
                      showarrow=False, font=dict(size=10), row=1, col=1)
    
    # Moment diagram
    fig.add_trace(go.Scatter(x=case.positions, y=case.moments, mode='lines', fill='tozeroy',
                            fillcolor='rgba(231,76,60,0.3)', line=dict(color='#E74C3C', width=2),
                            name='Moment', showlegend=False), row=2, col=1)
    mi = max(range(len(case.moments)), key=lambda i: abs(case.moments[i]))
    fig.add_annotation(x=case.positions[mi], y=case.moments[mi], 
                      text=f"M_max={case.moments[mi]:.1f} kN-m\n@ x={case.positions[mi]:.2f}m",
                      showarrow=True, arrowhead=2, font=dict(size=10), row=2, col=1)
    
    # Shear diagram
    fig.add_trace(go.Scatter(x=case.positions, y=case.shears, mode='lines', fill='tozeroy',
                            fillcolor='rgba(52,152,219,0.3)', line=dict(color='#3498DB', width=2),
                            name='Shear', showlegend=False), row=3, col=1)
    vi = max(range(len(case.shears)), key=lambda i: abs(case.shears[i]))
    fig.add_annotation(x=case.positions[vi], y=case.shears[vi],
                      text=f"V_max={abs(case.shears[vi]):.1f} kN",
                      showarrow=True, arrowhead=2, font=dict(size=10), row=3, col=1)
    
    # Update layout
    fig.update_xaxes(title_text="Position (m)", row=3, col=1)
    fig.update_yaxes(range=[-0.5, 0.9], row=1, col=1)
    fig.update_layout(height=600, showlegend=True, 
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5))
    
    return fig


def draw_util(ratios):
    names = list(ratios.keys())
    vals = list(ratios.values())
    colors = ['green' if v <= 1 else 'red' for v in vals]
    fig = go.Figure(data=[go.Bar(x=names, y=vals, marker_color=colors, text=[f'{v:.2f}' for v in vals], textposition='outside')])
    fig.add_hline(y=1.0, line_dash="dash", line_color="red")
    fig.update_layout(title="Utilization Ratios", yaxis_range=[0, max(max(vals)*1.2, 1.2)], height=280)
    return fig


def main():
    st.title("🏗️ Runway Beam Design V3.0")
    st.markdown("**AISC 360-16 (ASD) | DG7 | CMAA 70**")
    
    with st.sidebar:
        st.header("📋 Inputs")
        num_cranes = st.radio("Cranes:", [1, 2, 3], horizontal=True)
        
        # Initialize session state for crane data if not exists
        if 'crane_data' not in st.session_state:
            st.session_state.crane_data = {
                1: {'cap': 10.0, 'bridge_wt': 5.0, 'trolley_wt': 0.72, 'bridge_span': 20.0, 'min_approach': 1.0, 'wb': 3.15, 'buf_l': 0.266, 'buf_r': 0.266, 'nw': 2, 'iv': 25, 'ih': 20, 'il': 10, 'use_direct': False, 'direct_max': 62.96, 'direct_min': 13.08, 'direct_lat': 14.50},
                2: {'cap': 15.0, 'bridge_wt': 7.0, 'trolley_wt': 1.0, 'bridge_span': 20.0, 'min_approach': 1.2, 'wb': 3.5, 'buf_l': 0.30, 'buf_r': 0.30, 'nw': 2, 'iv': 25, 'ih': 20, 'il': 10, 'use_direct': False, 'direct_max': 80.0, 'direct_min': 20.0, 'direct_lat': 18.0},
                3: {'cap': 20.0, 'bridge_wt': 9.0, 'trolley_wt': 1.5, 'bridge_span': 22.0, 'min_approach': 1.5, 'wb': 4.0, 'buf_l': 0.35, 'buf_r': 0.35, 'nw': 2, 'iv': 25, 'ih': 20, 'il': 10, 'use_direct': False, 'direct_max': 100.0, 'direct_min': 25.0, 'direct_lat': 22.0},
            }
        
        cranes = []
        for i in range(1, num_cranes + 1):
            with st.expander(f"🏗️ Crane {i}", expanded=(i==1)):
                
                # Input method selection
                input_method = st.radio(
                    "Input Method:",
                    ["Calculate from crane data", "Direct wheel loads (from manufacturer)"],
                    key=f"input_method_{i}",
                    horizontal=True
                )
                use_direct = (input_method == "Direct wheel loads (from manufacturer)")
                
                st.markdown("---")
                
                if use_direct:
                    # Direct input from manufacturer data
                    st.markdown("**📋 Manufacturer Wheel Load Data:**")
                    c1, c2 = st.columns(2)
                    direct_max = c1.number_input("Max Wheel Load (kN)", 
                                                 value=max(float(st.session_state.crane_data[i].get('direct_max', 50.0)), 1.0),
                                                 key=f"direct_max_{i}", min_value=1.0, step=1.0,
                                                 help="Static max wheel load from crane datasheet (W_max)")
                    direct_min = c2.number_input("Min Wheel Load (kN)", 
                                                value=max(float(st.session_state.crane_data[i].get('direct_min', 10.0)), 0.0),
                                                key=f"direct_min_{i}", min_value=0.0, step=1.0,
                                                help="Static min wheel load from crane datasheet (W_min)")
                    direct_lat = c1.number_input("Lateral Load/Wheel (kN)", 
                                                value=max(float(st.session_state.crane_data[i].get('direct_lat', 5.0)), 0.0),
                                                key=f"direct_lat_{i}", min_value=0.0, step=0.5,
                                                help="Horizontal wheel load (Hs) from datasheet")
                    
                    # Still need these for geometry
                    cap = c2.number_input("Capacity (T)", value=max(float(st.session_state.crane_data[i].get('cap', 10.0)), 1.0), 
                                          key=f"cap_{i}", min_value=1.0, step=1.0,
                                          help="For reference only when using direct input")
                    bridge_wt, trolley_wt, bridge_span, min_approach = 0.0, 0.0, 20.0, 1.0
                    
                else:
                    # Calculate from crane parameters
                    st.markdown("**Crane Weights:**")
                    c1, c2 = st.columns(2)
                    cap = c1.number_input("Capacity (T)", value=max(float(st.session_state.crane_data[i].get('cap', 10.0)), 1.0), 
                                          key=f"cap_{i}", min_value=1.0, step=1.0)
                    bridge_wt = c2.number_input("Bridge Wt (T)", value=max(float(st.session_state.crane_data[i].get('bridge_wt', 5.0)), 0.5),
                                               key=f"bridge_wt_{i}", min_value=0.5, step=0.5,
                                               help="Weight of crane bridge without trolley")
                    c1, c2 = st.columns(2)
                    trolley_wt = c1.number_input("Trolley Wt (T)", value=max(float(st.session_state.crane_data[i].get('trolley_wt', 0.72)), 0.1),
                                                key=f"trolley_wt_{i}", min_value=0.1, step=0.1)
                    bridge_span = c2.number_input("Bridge Span (m)", value=max(float(st.session_state.crane_data[i].get('bridge_span', 20.0)), 5.0),
                                                 key=f"bridge_span_{i}", min_value=5.0, step=1.0,
                                                 help="Distance between runway rails")
                    
                    min_approach = c1.number_input("Min Hook Approach (m)", value=max(float(st.session_state.crane_data[i].get('min_approach', 1.0)), 0.3),
                                                  key=f"min_approach_{i}", min_value=0.3, step=0.1,
                                                  help="Minimum distance from hook CL to runway rail")
                    direct_max, direct_min, direct_lat = 0.0, 0.0, 0.0
                
                st.markdown("**Wheel Configuration:**")
                c1, c2 = st.columns(2)
                wb = c1.number_input("Wheel Base (m)", value=max(float(st.session_state.crane_data[i].get('wb', 2.2)), 0.5),
                                    key=f"wb_{i}", min_value=0.5, step=0.1,
                                    help="Center distance between wheels on same rail")
                nw = c2.number_input("Wheels/Rail", value=max(int(st.session_state.crane_data[i].get('nw', 2)), 2),
                                    key=f"nw_{i}", min_value=2, max_value=4,
                                    help="Number of axles per end truck")
                
                st.markdown("**Buffer Distances:**")
                c1, c2 = st.columns(2)
                buf_l = c1.number_input("Buffer Left (m)", value=max(float(st.session_state.crane_data[i].get('buf_l', 0.29)), 0.05),
                                    key=f"buf_l_{i}", min_value=0.05, step=0.05,
                                    help="Distance from left wheel to left buffer (aL)")
                buf_r = c2.number_input("Buffer Right (m)", value=max(float(st.session_state.crane_data[i].get('buf_r', 0.29)), 0.05),
                                    key=f"buf_r_{i}", min_value=0.05, step=0.05,
                                    help="Distance from right wheel to right buffer (aR)")
                
                st.markdown("**Impact Factors:**")
                c1, c2, c3 = st.columns(3)
                iv = c1.number_input("V %", value=int(st.session_state.crane_data[i].get('iv', 25)), key=f"iv_{i}",
                                    help="Vertical impact factor")
                ih = c2.number_input("H %", value=int(st.session_state.crane_data[i].get('ih', 20)), key=f"ih_{i}",
                                    help="Horizontal impact (if not using direct input)")
                il = c3.number_input("L %", value=int(st.session_state.crane_data[i].get('il', 10)), key=f"il_{i}",
                                    help="Longitudinal impact")
                
                # Update session state
                st.session_state.crane_data[i] = {
                    'cap': cap, 'bridge_wt': bridge_wt, 'trolley_wt': trolley_wt,
                    'bridge_span': bridge_span, 'min_approach': min_approach,
                    'wb': wb, 'buf_l': buf_l, 'buf_r': buf_r, 'nw': nw,
                    'iv': iv, 'ih': ih, 'il': il,
                    'use_direct': use_direct, 'direct_max': direct_max,
                    'direct_min': direct_min, 'direct_lat': direct_lat
                }
                
                # Create crane object
                crane = CraneData(
                    crane_id=i,
                    capacity_tonnes=cap,
                    bridge_weight=bridge_wt,
                    trolley_weight=trolley_wt,
                    bridge_span=bridge_span,
                    min_hook_approach=min_approach,
                    wheel_base=wb,
                    buffer_left=buf_l,
                    buffer_right=buf_r,
                    num_wheels=nw,
                    impact_v=iv/100,
                    impact_h=ih/100,
                    impact_l=il/100,
                    use_direct_input=use_direct,
                    direct_max_wheel_load=direct_max,
                    direct_min_wheel_load=direct_min,
                    direct_lateral_load=direct_lat
                )
                
                # Show calculated wheel loads
                max_wl, min_wl = crane.calc_wheel_loads()
                st.markdown("---")
                st.markdown("**📊 Wheel Loads for Design:**")
                col1, col2 = st.columns(2)
                col1.metric("Max Static", f"{max_wl:.2f} kN")
                col2.metric("Min Static", f"{min_wl:.2f} kN")
                col1.metric("Max + Impact", f"{crane.wheel_load_with_impact():.2f} kN")
                col2.metric("Lateral/wheel", f"{crane.lateral_per_wheel():.2f} kN")
                
                if use_direct:
                    st.caption("✅ Using manufacturer wheel load data")
                else:
                    st.caption(f"📐 Calculated: R_max={crane.R_max:.1f} kN, R_min={crane.R_min:.1f} kN")
                
                cranes.append(crane)
        
        st.subheader("📐 Geometry")
        c1, c2 = st.columns(2)
        beam_span = c1.number_input("Span m", value=4.5, min_value=3.0)
        Lb_m = c2.number_input("Lb m", value=4.5)
        rail_base = c1.number_input("Rail Base m", value=0.065, format="%.3f")
        rail_height = c2.number_input("Rail Ht m", value=0.065, format="%.3f")
        
        st.subheader("🔧 Material")
        c1, c2 = st.columns(2)
        steel = c1.selectbox("Grade", list(STEEL_GRADES.keys()), index=2)
        # Show selected steel properties immediately
        st.caption(f"📊 **{steel}:** Fy = {STEEL_GRADES[steel]['Fy']} MPa, Fu = {STEEL_GRADES[steel]['Fu']} MPa")
        
        crane_cls = c2.selectbox("Class", list(CRANE_CLASSES.keys()), index=2,
                                  format_func=lambda x: f"{x} - {CRANE_CLASSES[x]['name']}")
        # Show crane class description
        cls_info = CRANE_CLASSES[crane_cls]
        st.caption(f"📋 **Class {crane_cls}:** {cls_info['desc']}")
        st.caption(f"   Cycles: {cls_info['cycles']} | Deflection: L/{cls_info['defl_limit']}")
        
        fat_cat = c1.selectbox("Fatigue", list(FATIGUE_CATS.keys()), index=4,
                                format_func=lambda x: f"{x} - {FATIGUE_CATS[x]['desc'][:25]}...")
        # Show fatigue category description
        fat_info = FATIGUE_CATS[fat_cat]
        st.caption(f"🔩 **Category {fat_cat}:** {fat_info['desc']}")
        st.caption(f"   {fat_info['detail']}")
        st.caption(f"   Threshold: {fat_info['thresh']} MPa")
        
        # === STIFFENER OPTIONS ===
        st.subheader("🔩 Stiffeners")
        
        # Initialize stiffener data
        stiff_data = {
            'has_transverse': False,
            'trans_spacing': 1500,
            'trans_t': 10,
            'trans_b': 100,
            'has_bearing': False,
            'bearing_at_support': True,
            'bearing_at_load': True,
            'bearing_t': 12,
            'bearing_b': 120,
            'has_longitudinal': False,
            'long_position': 0.2,  # fraction of hw from compression flange
            'long_t': 10,
            'long_b': 80,
        }
        
        # Transverse Stiffeners
        has_transverse = st.checkbox("Transverse Stiffeners (Intermediate)", 
                                     help="Prevent web shear buckling, enable tension field action")
        stiff_data['has_transverse'] = has_transverse
        if has_transverse:
            c1, c2, c3 = st.columns(3)
            stiff_data['trans_spacing'] = c1.number_input("Spacing (mm)", value=1500, min_value=100, step=100,
                                        help="Spacing between transverse stiffeners", key="trans_spa")
            stiff_data['trans_t'] = c2.number_input("Thickness (mm)", value=10, min_value=6, step=2,
                                      help="Stiffener plate thickness", key="trans_t")
            stiff_data['trans_b'] = c3.number_input("Width (mm)", value=100, min_value=50, step=10,
                                      help="Stiffener width (one side of web)", key="trans_b")
        
        # Bearing Stiffeners
        has_bearing = st.checkbox("Bearing Stiffeners", 
                                  help="At supports and concentrated loads - prevent web yielding/crippling")
        stiff_data['has_bearing'] = has_bearing
        if has_bearing:
            c1, c2 = st.columns(2)
            stiff_data['bearing_at_support'] = c1.checkbox("At Supports", value=True, key="bear_sup")
            stiff_data['bearing_at_load'] = c2.checkbox("At Wheel Loads", value=True, key="bear_load")
            c1, c2 = st.columns(2)
            stiff_data['bearing_t'] = c1.number_input("Thickness (mm)", value=12, min_value=8, step=2,
                                      help="Bearing stiffener thickness", key="bear_t")
            stiff_data['bearing_b'] = c2.number_input("Width (mm)", value=120, min_value=50, step=10,
                                      help="Bearing stiffener width (one side)", key="bear_b")
        
        # Longitudinal Stiffeners
        has_longitudinal = st.checkbox("Longitudinal Stiffener", 
                                       help="For deep girders - prevents web bend-buckling")
        stiff_data['has_longitudinal'] = has_longitudinal
        if has_longitudinal:
            c1, c2, c3 = st.columns(3)
            stiff_data['long_position'] = c1.number_input("Position (×hw)", value=0.2, min_value=0.1, max_value=0.4, step=0.05,
                                      help="Distance from compression flange as fraction of hw", key="long_pos")
            stiff_data['long_t'] = c2.number_input("Thickness (mm)", value=10, min_value=6, step=2,
                                      help="Longitudinal stiffener thickness", key="long_t")
            stiff_data['long_b'] = c3.number_input("Width (mm)", value=80, min_value=40, step=10,
                                      help="Longitudinal stiffener width", key="long_b")
        
        # Weld Design (for built-up sections)
        st.markdown("---")
        st.markdown("**🔥 Weld Design**")
        weld_size = st.number_input("Fillet Weld Size (mm)", value=6, min_value=3, max_value=20, step=1,
                                    help="Fillet weld leg size for web-to-flange connection (AISC J2)")
        stiff_data['weld_size'] = weld_size
        
        # Legacy variables for compatibility
        has_stiff = has_transverse
        stiff_spa = stiff_data['trans_spacing'] if has_transverse else 0
        stiff_t = stiff_data['trans_t'] if has_transverse else 0
        stiff_b = stiff_data['trans_b'] if has_transverse else 0
        
        st.subheader("📏 Section")
        sec_choice = st.radio("Type:", ["Hot Rolled", "Built-up"], horizontal=True)
        cap_name, cap_data = "", {}
        
        if sec_choice == "Hot Rolled":
            fam = st.selectbox("Family:", list(SECTION_DB.keys()))
            sec_name = st.selectbox("Section:", list(SECTION_DB[fam].keys()))
            use_cap = st.checkbox("Cap Channel")
            if use_cap:
                cap_fam = st.selectbox("Channel:", list(CHANNEL_DB.keys()))
                cap_name = st.selectbox("Size:", list(CHANNEL_DB[cap_fam].keys()))
                cap_data = CHANNEL_DB[cap_fam][cap_name]
        else:
            c1, c2 = st.columns(2)
            bu_d = c1.number_input("d mm", value=500)
            bu_bft = c2.number_input("bf_top mm", value=200)
            bu_tft = c1.number_input("tf_top mm", value=16)
            bu_bfb = c2.number_input("bf_bot mm", value=150)
            bu_tfb = c1.number_input("tf_bot mm", value=12)
            bu_tw = c2.number_input("tw mm", value=10)
            use_cap = st.checkbox("Cap Channel", key="bu_cap")
            if use_cap:
                cap_fam = st.selectbox("Channel:", list(CHANNEL_DB.keys()), key="bcf")
                cap_name = st.selectbox("Size:", list(CHANNEL_DB[cap_fam].keys()), key="bcs")
                cap_data = CHANNEL_DB[cap_fam][cap_name]
        
        # Project Info for PDF Report
        with st.expander("📋 Project Info (for PDF)", expanded=False):
            st.session_state['project_name'] = st.text_input("Project Name", 
                value=st.session_state.get('project_name', 'Crane Runway Beam Design'))
            st.session_state['designer'] = st.text_input("Designer", 
                value=st.session_state.get('designer', 'Engineer'))
        
        st.markdown("---")
        run_btn = st.button("🚀 Run Design", type="primary", use_container_width=True)
        fatigue_btn = st.button("🔄 Run Fatigue Check", type="secondary", use_container_width=True)
    
    # Initialize session state for results
    if 'design_results' not in st.session_state:
        st.session_state.design_results = None
    if 'fatigue_results' not in st.session_state:
        st.session_state.fatigue_results = None
    
    if run_btn:
        # Store inputs in session state for persistence
        st.session_state.run_design = True
        st.session_state.run_fatigue = False  # Reset fatigue when new design runs
        st.session_state.fatigue_results = None
        st.session_state.design_inputs = {
            'cranes': cranes,
            'beam_span': beam_span,
            'Lb_m': Lb_m,
            'rail_base': rail_base,
            'rail_height': rail_height,
            'steel': steel,
            'crane_cls': crane_cls,
            'fat_cat': fat_cat,
            'has_stiff': has_stiff,
            'stiff_spa': stiff_spa,
            'stiff_t': stiff_t,
            'stiff_b': stiff_b,
            'stiff_data': stiff_data,  # Full stiffener data
            'sec_choice': sec_choice,
            'use_cap': use_cap,
            'cap_name': cap_name,
            'cap_data': cap_data,
        }
        if sec_choice == "Hot Rolled":
            st.session_state.design_inputs['fam'] = fam
            st.session_state.design_inputs['sec_name'] = sec_name
        else:
            st.session_state.design_inputs['bu_d'] = bu_d
            st.session_state.design_inputs['bu_bft'] = bu_bft
            st.session_state.design_inputs['bu_tft'] = bu_tft
            st.session_state.design_inputs['bu_bfb'] = bu_bfb
            st.session_state.design_inputs['bu_tfb'] = bu_tfb
            st.session_state.design_inputs['bu_tw'] = bu_tw
    
    # Handle fatigue button click
    if fatigue_btn:
        if st.session_state.get('design_results'):
            st.session_state.run_fatigue = True
            dr = st.session_state.design_results
            fat_result = check_fatigue(dr['sec'], dr['M'], CRANE_CLASSES[dr['crane_cls']]['max_cycles'], dr['fat_cat'])
            st.session_state.fatigue_results = fat_result
        else:
            st.warning("⚠️ Please run design first before running fatigue check.")
    
    # Run design if we have stored inputs
    if st.session_state.get('run_design', False):
        inputs = st.session_state.design_inputs
        cranes = inputs['cranes']
        beam_span = inputs['beam_span']
        Lb_m = inputs['Lb_m']
        rail_base = inputs['rail_base']
        rail_height = inputs['rail_height']
        steel = inputs['steel']
        crane_cls = inputs['crane_cls']
        fat_cat = inputs['fat_cat']
        has_stiff = inputs['has_stiff']
        stiff_spa = inputs['stiff_spa']
        stiff_t = inputs.get('stiff_t', 10)
        stiff_b = inputs.get('stiff_b', 100)
        stiff_data = inputs.get('stiff_data', {
            'has_transverse': has_stiff,
            'trans_spacing': stiff_spa,
            'trans_t': stiff_t,
            'trans_b': stiff_b,
            'has_bearing': False,
            'has_longitudinal': False
        })
        sec_choice = inputs['sec_choice']
        use_cap = inputs['use_cap']
        cap_name = inputs['cap_name']
        cap_data = inputs['cap_data']
        
        Fy, Fu = STEEL_GRADES[steel]['Fy'], STEEL_GRADES[steel]['Fu']
        Lb = Lb_m * 1000
        
        if sec_choice == "Hot Rolled":
            fam = inputs.get('fam', 'IPE')
            sec_name = inputs.get('sec_name', 'IPE 300')
            props = SECTION_DB[fam][sec_name]
            sec = Section(name=sec_name, sec_type='hot_rolled', d=props['d'], bf_top=props['bf'], tf_top=props['tf'], bf_bot=props['bf'], tf_bot=props['tf'], tw=props['tw'])
            sec.hw = sec.d - 2*sec.tf_top
            sec.Ix, sec.Iy, sec.Sx, sec.A, sec.mass = props['Ix'], props['Iy'], props['Sx'], props['A'], props['mass']
            sec.rx, sec.ry = math.sqrt(sec.Ix/sec.A), math.sqrt(sec.Iy/sec.A)
            sec.Zx = sec.Sx * 1.12
            sec.J = props['bf']*props['tf']**3/3*2 + sec.hw*props['tw']**3/3
            sec.ho = sec.d - props['tf']
            sec.Cw = sec.Iy * sec.ho**2 / 4
            sec.rts = math.sqrt(math.sqrt(sec.Iy*sec.Cw)/sec.Sx) if sec.Sx > 0 else 1
            sec.y_bar = sec.d / 2
            sec.Sy = sec.Iy / (props['bf']/2)
        else:
            bu_d = inputs.get('bu_d', 500)
            bu_bft = inputs.get('bu_bft', 200)
            bu_tft = inputs.get('bu_tft', 16)
            bu_bfb = inputs.get('bu_bfb', 150)
            bu_tfb = inputs.get('bu_tfb', 12)
            bu_tw = inputs.get('bu_tw', 10)
            hw = bu_d - bu_tft - bu_tfb
            sec = Section(name="Built-up", sec_type='built_up', d=bu_d, bf_top=bu_bft, tf_top=bu_tft, bf_bot=bu_bfb, tf_bot=bu_tfb, tw=bu_tw, hw=hw)
            sec.calc_props()
        
        if use_cap and cap_data:
            sec.has_cap, sec.cap_name = True, cap_name
            sec.cap_A, sec.cap_Iy, sec.cap_d = cap_data['A'], cap_data['Iy'], cap_data['d']
            sec.cap_cy = cap_data.get('cy', cap_data['d']/2)
            sec.calc_props()
        
        cases = find_critical(beam_span, cranes)
        gov = get_governing(cases)
        
        if not gov:
            st.error("No valid load cases!")
            return
        
        mc, sc, rc = gov['moment'], gov['shear'], gov['reaction']
        cmp = check_compact(sec, Fy)
        
        # Web slenderness parameters
        h_tw = sec.hw / max(sec.tw, 1)
        lambda_rw = 5.70 * math.sqrt(E_STEEL / Fy)
        
        # Built-up sections ALWAYS use plate girder design (AISC F4/F5 & G)
        is_plate_girder = (sec.sec_type == 'built_up')
        
        Rpg, aw, Cv = 1.0, 0.0, 1.0  # Default values
        if is_plate_girder:
            # Use plate girder provisions (AISC F4/F5)
            result = calc_plate_girder_Mn(sec, Fy, Lb, cmp)
            Mn, Lp, Lr, ltb, Rpg, aw = result
            # Use plate girder shear with tension field action option
            Vn, Cv = calc_Vn_plate_girder(sec, Fy, has_stiff, stiff_spa, use_tfa=has_stiff)
        else:
            # Standard design for hot-rolled sections (AISC F2/F3)
            Mn, Lp, Lr, ltb = calc_Mn(sec, Fy, Lb, cmp)
            Vn, Cv = calc_Vn(sec, Fy, has_stiff, stiff_spa)
        
        # Beam self-weight (uniform load)
        w_self = sec.mass * GRAVITY / 1000  # kN/m (mass in kg/m × 9.81 / 1000)
        R_self = w_self * beam_span / 2  # Reaction from self-weight (simply supported)
        M_self = w_self * beam_span**2 / 8  # Moment from self-weight
        V_self = w_self * beam_span / 2  # Shear from self-weight
        
        # Total loads (crane + self-weight)
        M = abs(mc.M_max) + M_self
        V = sc.V_max + V_self
        R_crane = max(rc.R_left, rc.R_right)
        R = R_crane + R_self  # Total reaction including self-weight
        
        max_Ph = max(c.lateral_per_wheel() for c in cranes)
        M_lat = max_Ph * (rail_height*1000 + 50) / 1000
        
        Omega_b, Omega_v = 1.67, 1.50
        fb = M / (Mn / Omega_b) if Mn > 0 else 999
        fv = V / (Vn / Omega_v) if Vn > 0 else 999
        
        lb_mm = rail_base * 1000 + 20
        max_Pv = max(c.wheel_load_with_impact() for c in cranes)
        Rn_wly, Rn_wcr = check_wly(sec, Fy, lb_mm), check_wcr(sec, Fy, lb_mm)
        f_wly = max_Pv / (Rn_wly / 1.50) if Rn_wly > 0 else 999
        f_wcr = max_Pv / (Rn_wcr / 2.00) if Rn_wcr > 0 else 999
        
        dl = CRANE_CLASSES[crane_cls]['defl_limit']
        delta = calc_defl(sec, max(c.calc_wheel_loads()[0] for c in cranes), beam_span, max(c.wheel_base for c in cranes))
        delta_lim = beam_span * 1000 / dl
        f_defl = delta / delta_lim if delta_lim > 0 else 999
        
        fat = {'sr': 0, 'Fsr': 0, 'ratio': 0, 'status': 'Not Run'}  # Initialize fatigue as not run
        Mn_y = Fy * sec.Sy * 1.12 / 1e6 if sec.Sy > 0 else Mn * 0.3
        f_lat = M_lat / (Mn_y / Omega_b) if Mn_y > 0 else 999
        
        # Ratios WITHOUT fatigue (fatigue is separate)
        ratios = {'Flexure': fb, 'Lateral': f_lat, 'Combined': fb+f_lat, 'Shear': fv, 'WebYld': f_wly, 'WebCrp': f_wcr, 'Defl': f_defl}
        gov_ratio = max(ratios.values())
        gov_check = max(ratios, key=ratios.get)
        is_ok = gov_ratio <= 1.0
        
        # Store design results for fatigue check later
        st.session_state.design_results = {
            'sec': sec, 'M': M, 'crane_cls': crane_cls, 'fat_cat': fat_cat,
            'Fy': Fy, 'Mn': Mn, 'Omega_b': Omega_b
        }
        
        if is_ok:
            st.success(f"✅ DESIGN ADEQUATE | Util: {gov_ratio:.0%} | Gov: {gov_check}")
        else:
            st.error(f"❌ DESIGN NOT ADEQUATE | Util: {gov_ratio:.0%} | Gov: {gov_check}")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Utilization", f"{gov_ratio:.2f}")
        c2.metric("Governing", gov_check)
        c3.metric("Section", sec.name[:15])
        c4.metric("Fy", f"{Fy} MPa")
        c5.metric("Weight", f"{sec.mass:.1f} kg/m")
        
        tabs = st.tabs(["📊 Loads", "📈 Diagrams", "📐 Section", "💪 Checks", "🔄 Fatigue", "🔩 Reactions", "📝 Calcs"])
        
        with tabs[0]:
            st.subheader("📊 Critical Load Cases")
            
            # Crane summary
            st.markdown("**Crane Summary:**")
            crane_summary = []
            for crane in cranes:
                max_wl, min_wl = crane.calc_wheel_loads()
                crane_summary.append({
                    'Crane': f"Crane {crane.crane_id}",
                    'Capacity (T)': f"{crane.capacity_tonnes:.1f}",
                    'Bridge (T)': f"{crane.bridge_weight:.1f}",
                    'Trolley (T)': f"{crane.trolley_weight:.2f}",
                    'Span (m)': f"{crane.bridge_span:.1f}",
                    'Wheel Base (m)': f"{crane.wheel_base:.2f}",
                    'Max Wheel (kN)': f"{max_wl:.1f}",
                    'With Impact (kN)': f"{crane.wheel_load_with_impact():.1f}",
                })
            st.dataframe(pd.DataFrame(crane_summary), hide_index=True, use_container_width=True)
            
            st.markdown("---")
            st.markdown(f"**Governing Results (Crane Loads Only):**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Max Moment (crane)", f"{mc.M_max:.2f} kN-m", f"@ {mc.M_pos:.2f}m")
            col2.metric("Max Shear (crane)", f"{sc.V_max:.2f} kN", f"@ {sc.V_pos:.2f}m")
            col3.metric("Max Reaction (crane)", f"{R_crane:.2f} kN")
            
            st.markdown(f"**Total Design Values (Crane + Self-Weight):**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Moment", f"{M:.2f} kN-m", f"+{M_self:.2f} self-wt")
            col2.metric("Total Shear", f"{V:.2f} kN", f"+{V_self:.2f} self-wt")
            col3.metric("Total Reaction", f"{R:.2f} kN", f"+{R_self:.2f} self-wt")
            
            st.markdown("---")
            st.markdown("**All Load Cases (Crane Loads):**")
            case_data = []
            for c in cases:
                case_data.append({
                    'Load Case': c.desc,
                    'M_max (kN-m)': f"{c.M_max:.1f}",
                    'M @ (m)': f"{c.M_pos:.2f}",
                    'V_max (kN)': f"{c.V_max:.1f}",
                    'R_L (kN)': f"{c.R_left:.1f}",
                    'R_R (kN)': f"{c.R_right:.1f}",
                    'Wheels': len(c.wheels)
                })
            st.dataframe(pd.DataFrame(case_data), hide_index=True, use_container_width=True)
        
        with tabs[1]:
            sel = st.selectbox("Case:", [c.desc for c in cases])
            case = next((c for c in cases if c.desc == sel), cases[0])
            st.plotly_chart(draw_beam(case, beam_span), use_container_width=True)
        
        with tabs[2]:
            st.subheader("📐 Section & Stiffener Arrangement")
            
            # Section drawing
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(draw_section(sec), use_container_width=True)
            with c2:
                st.markdown("**Section Properties:**")
                st.markdown(f"**d** = {sec.d:.0f} mm | **hw** = {sec.hw:.0f} mm | **tw** = {sec.tw:.0f} mm")
                st.markdown(f"**Top Flange:** {sec.bf_top:.0f} × {sec.tf_top:.0f} mm")
                st.markdown(f"**Bot Flange:** {sec.bf_bot:.0f} × {sec.tf_bot:.0f} mm")
                st.markdown(f"**A** = {sec.A:.0f} mm² | **Ix** = {sec.Ix/1e6:.2f}×10⁶ mm⁴")
                st.markdown(f"**Sx** = {sec.Sx/1e3:.1f}×10³ mm³ | **Weight** = {sec.mass:.1f} kg/m")
                st.markdown(f"**Compactness:** Flange={cmp['flg']}, Web={cmp['web']}")
            
            # Beam elevation with stiffeners
            st.markdown("---")
            st.plotly_chart(draw_beam_elevation(sec, beam_span, stiff_data), use_container_width=True)
            
            # Stiffener checks (for built-up sections)
            if is_plate_girder and (stiff_data.get('has_transverse') or stiff_data.get('has_bearing') or stiff_data.get('has_longitudinal')):
                st.markdown("---")
                st.subheader("🔩 Stiffener Design Checks")
                
                # Transverse stiffener check
                if stiff_data.get('has_transverse'):
                    with st.expander("**Transverse Stiffeners (AISC G2.2)**", expanded=True):
                        trans_check = check_transverse_stiffener(sec, Fy, stiff_data)
                        if trans_check['ok']:
                            st.success("✅ Transverse Stiffeners OK")
                        else:
                            st.error("❌ Transverse Stiffeners NOT OK")
                        
                        for chk in trans_check['checks']:
                            status = "✅" if chk['ok'] else "❌"
                            st.markdown(f"- {chk['name']}: {chk['demand']} ≤ {chk['capacity']} {status}")
                
                # Bearing stiffener check
                if stiff_data.get('has_bearing'):
                    with st.expander("**Bearing Stiffeners (AISC J10.8)**", expanded=True):
                        # Check at support
                        if stiff_data.get('bearing_at_support'):
                            bear_check_sup = check_bearing_stiffener(sec, Fy, R, stiff_data, at_support=True)
                            st.markdown("**At Supports:**")
                            if bear_check_sup['ok']:
                                st.success(f"✅ Bearing Stiffener OK (Ratio: {bear_check_sup['ratio']:.2f})")
                            else:
                                st.error(f"❌ Bearing Stiffener NOT OK (Ratio: {bear_check_sup['ratio']:.2f})")
                            for chk in bear_check_sup['checks']:
                                status = "✅" if chk['ok'] else "❌"
                                st.markdown(f"- {chk['name']}: {chk['demand']} ≤ {chk['capacity']} {status}")
                        
                        # Check at wheel loads
                        if stiff_data.get('bearing_at_load'):
                            bear_check_load = check_bearing_stiffener(sec, Fy, max_Pv, stiff_data, at_support=False)
                            st.markdown("**At Wheel Loads:**")
                            if bear_check_load['ok']:
                                st.success(f"✅ Bearing Stiffener OK (Ratio: {bear_check_load['ratio']:.2f})")
                            else:
                                st.error(f"❌ Bearing Stiffener NOT OK (Ratio: {bear_check_load['ratio']:.2f})")
                            for chk in bear_check_load['checks']:
                                status = "✅" if chk['ok'] else "❌"
                                st.markdown(f"- {chk['name']}: {chk['demand']} ≤ {chk['capacity']} {status}")
                
                # Longitudinal stiffener check
                if stiff_data.get('has_longitudinal'):
                    with st.expander("**Longitudinal Stiffener (AISC F5)**", expanded=True):
                        long_check = check_longitudinal_stiffener(sec, Fy, stiff_data)
                        if long_check['ok']:
                            st.success("✅ Longitudinal Stiffener OK")
                        else:
                            st.error("❌ Longitudinal Stiffener NOT OK")
                        
                        for chk in long_check['checks']:
                            status = "✅" if chk['ok'] else "❌"
                            st.markdown(f"- {chk['name']}: {chk['demand']} ≤ {chk['capacity']} {status}")
        
        with tabs[3]:
            st.plotly_chart(draw_util(ratios), use_container_width=True)
            st.markdown(f"**LTB:** Lp={Lp/1000:.2f}m, Lr={Lr/1000:.2f}m, Lb={Lb/1000:.2f}m → {ltb}")
            
            # Show plate girder info for built-up sections
            if is_plate_girder:
                web_class = "Slender" if h_tw > lambda_rw else ("Noncompact" if h_tw > 3.76*math.sqrt(E_STEEL/Fy) else "Compact")
                st.info(f"🔧 **Plate Girder Design (AISC F4/F5 & G)** | Web: {web_class} (h/tw = {h_tw:.1f})")
                col1, col2, col3 = st.columns(3)
                col1.metric("Rpg (bending reduction)", f"{Rpg:.3f}")
                col2.metric("aw (Aw/Afc)", f"{aw:.2f}")
                col3.metric("Cv (shear coefficient)", f"{Cv:.3f}")
            
            checks = [
                ['Flexure', f"{M:.1f} kN-m", f"{Mn/Omega_b:.1f} kN-m", f"{fb:.3f}", '✅' if fb<=1 else '❌'],
                ['Lateral', f"{M_lat:.1f} kN-m", f"{Mn_y/Omega_b:.1f} kN-m", f"{f_lat:.3f}", '✅' if f_lat<=1 else '❌'],
                ['Shear', f"{V:.1f} kN", f"{Vn/Omega_v:.1f} kN", f"{fv:.3f}", '✅' if fv<=1 else '❌'],
                ['Deflection', f"{delta:.1f} mm", f"{delta_lim:.1f} mm", f"{f_defl:.3f}", '✅' if f_defl<=1 else '❌'],
                ['Web Yielding', f"{max_Pv:.1f} kN", f"{Rn_wly/1.50:.1f} kN", f"{f_wly:.3f}", '✅' if f_wly<=1 else '❌'],
                ['Web Crippling', f"{max_Pv:.1f} kN", f"{Rn_wcr/2.00:.1f} kN", f"{f_wcr:.3f}", '✅' if f_wcr<=1 else '❌'],
            ]
            st.dataframe(pd.DataFrame(checks, columns=['Check', 'Demand', 'Capacity', 'Ratio', 'Status']), hide_index=True)
            st.info("💡 Fatigue check is separate - use 'Run Fatigue Check' button")
        
        with tabs[4]:
            st.subheader("🔄 Fatigue Check (AISC 360-16 Appendix 3)")
            
            # Check if fatigue has been run
            if st.session_state.get('run_fatigue', False) and st.session_state.get('fatigue_results'):
                fat = st.session_state.fatigue_results
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Stress Range (sr)", f"{fat['sr']:.1f} MPa")
                col2.metric("Allowable (Fsr)", f"{fat['Fsr']:.1f} MPa")
                col3.metric("Ratio", f"{fat['ratio']:.3f}")
                
                if fat['ratio'] <= 1.0:
                    st.success(f"✅ FATIGUE OK | Ratio: {fat['ratio']:.3f}")
                else:
                    st.error(f"❌ FATIGUE NOT OK | Ratio: {fat['ratio']:.3f}")
                
                st.markdown("---")
                st.markdown("**Fatigue Parameters:**")
                col1, col2 = st.columns(2)
                col1.markdown(f"- **Crane Class:** {crane_cls}")
                col1.markdown(f"- **Design Cycles:** {CRANE_CLASSES[crane_cls]['max_cycles']:,}")
                col2.markdown(f"- **Fatigue Category:** {fat_cat}")
                col2.markdown(f"- **Threshold Stress (FTH):** {FATIGUE_CATS[fat_cat]['thresh']} MPa")
                
                st.markdown("---")
                st.markdown("**Calculation:**")
                st.latex(r"f_{sr} = \frac{M_{range}}{S_x} = \frac{" + f"{M*1e6:.0f}" + r"}{" + f"{sec.Sx:.0f}" + r"} = " + f"{fat['sr']:.1f}" + r" \text{{ MPa}}")
                st.latex(r"F_{sr} = \left(\frac{C_f}{n}\right)^{0.333} \geq F_{TH}")
                
            else:
                st.warning("⚠️ Fatigue check not run yet. Click 'Run Fatigue Check' button in sidebar.")
                st.markdown("---")
                st.markdown("**Current Settings:**")
                col1, col2 = st.columns(2)
                col1.markdown(f"- **Crane Class:** {crane_cls}")
                col1.markdown(f"- **Design Cycles:** {CRANE_CLASSES[crane_cls]['max_cycles']:,}")
                col2.markdown(f"- **Fatigue Category:** {fat_cat}")
                col2.markdown(f"- **Threshold Stress (FTH):** {FATIGUE_CATS[fat_cat]['thresh']} MPa")
        
        with tabs[5]:
            st.subheader("🔩 Crane Bridge Analysis & Runway Beam Loads")
            
            # Show bridge calculations for each crane
            for crane in cranes:
                max_wl, min_wl = crane.calc_wheel_loads()
                with st.expander(f"🏗️ Crane {crane.crane_id} - {crane.capacity_tonnes:.0f}T Capacity", expanded=True):
                    
                    # Bridge diagram
                    st.markdown("**Bridge Load Analysis:**")
                    st.markdown(f"""
                    ```
                    Trolley + Load = {(crane.capacity_tonnes + crane.trolley_weight)*GRAVITY:.1f} kN (moving)
                              ↓
                    ══════════●══════════════════════
                    △                               △
                  Rail A                          Rail B
                  (Near)                          (Far)
                    ├─── {crane.min_hook_approach:.1f}m ───┤
                    ├────────── {crane.bridge_span:.1f}m ──────────┤
                    ```
                    """)
                    
                    c1, c2, c3 = st.columns(3)
                    
                    c1.markdown("**Input Parameters:**")
                    c1.caption(f"• Capacity: {crane.capacity_tonnes:.1f} T")
                    c1.caption(f"• Bridge Weight: {crane.bridge_weight:.1f} T")
                    c1.caption(f"• Trolley Weight: {crane.trolley_weight:.2f} T")
                    c1.caption(f"• Bridge Span: {crane.bridge_span:.1f} m")
                    c1.caption(f"• Min Hook Approach: {crane.min_hook_approach:.1f} m")
                    
                    c2.markdown("**End Truck Reactions:**")
                    c2.metric("R_max (trolley near)", f"{crane.R_max:.1f} kN")
                    c2.metric("R_min (trolley far)", f"{crane.R_min:.1f} kN")
                    c2.caption(f"Ratio R_max/R_min = {crane.R_max/crane.R_min:.2f}")
                    
                    c3.markdown("**Wheel Loads ({} wheels):**".format(crane.num_wheels))
                    c3.caption(f"• Max Static: {max_wl:.1f} kN")
                    c3.caption(f"• Min Static: {min_wl:.1f} kN")
                    c3.caption(f"• **Max + Impact: {crane.wheel_load_with_impact():.1f} kN**")
                    c3.caption(f"• Lateral/wheel: {crane.lateral_per_wheel():.1f} kN")
                    c3.caption(f"• Longitudinal: {crane.longitudinal_force():.1f} kN")
            
            st.markdown("---")
            st.subheader("📊 Design Loads for Runway Beam")
            
            # Summary table
            st.markdown("**Maximum Wheel Loads (with impact) for Design:**")
            wheel_summary = []
            for crane in cranes:
                crane.calc_wheel_loads()
                wheel_summary.append({
                    'Crane': f"Crane {crane.crane_id}",
                    'Capacity': f"{crane.capacity_tonnes:.0f} T",
                    'Bridge Span': f"{crane.bridge_span:.1f} m",
                    'R_max': f"{crane.R_max:.1f} kN",
                    'R_min': f"{crane.R_min:.1f} kN",
                    'Max Wheel (static)': f"{crane.max_wheel_load:.1f} kN",
                    'Max Wheel (+impact)': f"{crane.wheel_load_with_impact():.1f} kN",
                    'Lateral/wheel': f"{crane.lateral_per_wheel():.1f} kN",
                })
            st.dataframe(pd.DataFrame(wheel_summary), hide_index=True, use_container_width=True)
            
            st.markdown("---")
            st.subheader("📊 Design Loads for Runway Beam")
            
            # Self-weight info
            st.markdown("**Beam Self-Weight:**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Unit Weight", f"{w_self:.3f} kN/m")
            col2.metric("R_self (per support)", f"{R_self:.2f} kN")
            col3.metric("M_self", f"{M_self:.2f} kN-m")
            
            st.markdown("---")
            st.markdown("**Critical Support Reactions (from Max Reaction Case):**")
            
            # Calculate lateral and longitudinal forces
            total_lateral = sum(c.lateral_per_wheel() * c.num_wheels for c in cranes)
            max_longitudinal = max(c.longitudinal_force() for c in cranes)
            
            # Determine which side has max reaction
            if rc.R_left >= rc.R_right:
                R_max_crane = rc.R_left
                R_min_crane = rc.R_right
                max_label = "Left Support"
                min_label = "Right Support"
            else:
                R_max_crane = rc.R_right
                R_min_crane = rc.R_left
                max_label = "Right Support"
                min_label = "Left Support"
            
            # Create a table for reactions
            st.markdown(f"**Load Case:** {rc.desc if hasattr(rc, 'desc') else 'Max Reaction'}")
            
            col1, col2, col3 = st.columns(3)
            
            col1.markdown(f"**{max_label}**")
            col1.metric("Vertical (V)", f"{R_max_crane + R_self:.2f} kN", 
                       delta=f"Crane: {R_max_crane:.1f} + Self: {R_self:.1f}")
            col1.metric("Horizontal (H)", f"{total_lateral:.2f} kN",
                       help="Total lateral thrust from all crane wheels")
            col1.metric("Longitudinal (L)", f"{max_longitudinal:.2f} kN",
                       help="Longitudinal force from crane acceleration/braking")
            
            col2.markdown(f"**{min_label}**")
            col2.metric("Vertical (V)", f"{R_min_crane + R_self:.2f} kN",
                       delta=f"Crane: {R_min_crane:.1f} + Self: {R_self:.1f}")
            col2.metric("Horizontal (H)", f"{total_lateral:.2f} kN",
                       help="Total lateral thrust from all crane wheels")
            col2.metric("Longitudinal (L)", f"{max_longitudinal:.2f} kN",
                       help="Longitudinal force from crane acceleration/braking")
            
            col3.markdown("**Notes:**")
            col3.caption("• Vertical includes beam self-weight")
            col3.caption("• Horizontal = Lateral thrust (both supports resist)")
            col3.caption("• Longitudinal = Crane braking/acceleration")
            col3.caption("• H and L are shown at both supports (design both brackets for full load)")
            
            st.markdown("---")
            st.markdown("**Reaction Summary Table:**")
            reaction_data = {
                'Reaction Type': ['Vertical (V)', 'Horizontal (H)', 'Longitudinal (L)'],
                max_label: [
                    f"{R_max_crane + R_self:.2f} kN",
                    f"{total_lateral:.2f} kN",
                    f"{max_longitudinal:.2f} kN"
                ],
                min_label: [
                    f"{R_min_crane + R_self:.2f} kN",
                    f"{total_lateral:.2f} kN",
                    f"{max_longitudinal:.2f} kN"
                ],
                'Notes': [
                    'Crane + Self-weight',
                    'Lateral thrust (both supports)',
                    'Braking/acceleration'
                ]
            }
            st.dataframe(pd.DataFrame(reaction_data), hide_index=True, use_container_width=True)
            
            st.info("💡 **Note:** Horizontal and Longitudinal forces should be applied at both supports for bracket design. Wheel loads vary based on trolley position on the bridge.")
        
        with tabs[6]:
            st.subheader("📋 Detailed Design Calculations")
            st.markdown("*Per AISC 360-16 (ASD), Design Guide 7, CMAA 70*")
            
            # Generate detailed calculations
            detailed_calcs = gen_detailed_calcs(
                sec, Fy, Fu, cmp, gov, beam_span, crane_cls, fat_cat, Lb, 
                has_stiff, stiff_spa, cranes, w_self, R_self, M_self, V_self, M_lat, ratios,
                weld_size=stiff_data.get('weld_size', 6), delta_actual=delta
            )
            
            # Display each section with proper formatting
            for section in detailed_calcs:
                with st.expander(f"**{section['title']}**" + (f" — *{section['ref']}*" if section['ref'] else ""), expanded=True):
                    # Display content items
                    if section.get('content'):
                        for item in section['content']:
                            if len(item) == 2:
                                label, value = item
                                st.markdown(f"**{label}:** {value}")
                    
                    # Display calculations
                    if section.get('calculations'):
                        st.markdown("---")
                        for calc in section['calculations']:
                            if len(calc) == 3:
                                name, formula, result = calc
                                if name and name.startswith('**'):
                                    st.markdown(f"\n{name}")
                                elif name:
                                    col1, col2, col3 = st.columns([2, 3, 3])
                                    with col1:
                                        st.markdown(f"**{name}**")
                                    with col2:
                                        if formula:
                                            st.latex(formula.replace('$', ''))
                                    with col3:
                                        if result:
                                            if '✓' in result or '✗' in result:
                                                if '✓' in result:
                                                    st.success(result)
                                                else:
                                                    st.error(result)
                                            else:
                                                st.markdown(result)
            
            st.markdown("---")
            
            # Export options
            st.subheader("📥 Export Report")
            
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                # PDF Export
                if PDF_AVAILABLE:
                    if st.button("📄 Generate PDF Report", type="primary"):
                        with st.spinner("Generating PDF report..."):
                            try:
                                project_info = {
                                    'project': st.session_state.get('project_name', 'Crane Runway Beam Design'),
                                    'designer': st.session_state.get('designer', 'Engineer'),
                                }
                                
                                pdf_bytes = generate_pdf_report(
                                    sec, Fy, Fu, cmp, gov, beam_span, crane_cls, fat_cat, Lb, 
                                    has_stiff, stiff_spa, cranes, w_self, R_self, M_self, V_self, 
                                    M_lat, ratios, 
                                    weld_size=stiff_data.get('weld_size', 6) if stiff_data else 6,
                                    delta_actual=delta if 'delta' in dir() else 0,
                                    project_info=project_info
                                )
                                
                                if pdf_bytes:
                                    st.download_button(
                                        "⬇️ Download PDF",
                                        data=pdf_bytes,
                                        file_name=f"runway_beam_design_{sec.name.replace(' ', '_')}.pdf",
                                        mime="application/pdf"
                                    )
                                    st.success("✅ PDF generated successfully!")
                                else:
                                    st.error("Failed to generate PDF")
                            except Exception as e:
                                st.error(f"Error generating PDF: {str(e)}")
                else:
                    st.warning("PDF export requires reportlab library. Install with: `pip install reportlab`")
            
            with col_exp2:
                # Text Export
                with st.expander("📝 Text Version"):
                    calc_text = gen_calcs(sec, Fy, Fu, cmp, gov, beam_span, crane_cls, fat_cat, Lb, has_stiff, stiff_spa)
                    st.text_area("Calculations", calc_text, height=200)
                    st.download_button("📥 Download TXT", calc_text, "calculations.txt")
    
    # Show info only if design hasn't been run yet
    if not st.session_state.get('run_design', False):
        st.info("👈 Enter parameters and click Run Design")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🏭 Crane Service Classes (CMAA 70)
            
            | Class | Name | Cycles | Defl. | Application |
            |:-----:|:-----|:------:|:-----:|:------------|
            | **A** | Standby | 20K-100K | L/600 | Powerhouses, transformer stations |
            | **B** | Light | 100K-500K | L/600 | Repair shops, light assembly |
            | **C** | Moderate | 500K-2M | L/600 | Machine shops, paper mills |
            | **D** | Heavy | 2M-10M | L/800 | Fabrication shops, steel warehouses |
            | **E** | Severe | 10M-20M | L/1000 | Scrap yards, container handling |
            | **F** | Continuous | >20M | L/1000 | Steel mills, foundries |
            
            *Select based on expected crane usage intensity and cycles over design life*
            """)
        
        with col2:
            st.markdown("""
            ### 🔩 Fatigue Categories (AISC 360-16 App.3)
            
            | Cat | Threshold | Typical Detail |
            |:---:|:---------:|:---------------|
            | **A** | 165 MPa | Plain base metal, rolled surfaces |
            | **B** | 110 MPa | Continuous fillet welds, groove welds |
            | **C** | 69 MPa | Transverse stiffeners, short attachments |
            | **D** | 48 MPa | Longitudinal attachments 50-100mm |
            | **E** | 31 MPa | Long attachments >100mm, cover plates |
            | **F** | 55 MPa | Fillet welds in shear |
            
            *For runway beams, Category E (flange-web welds) is typical*
            """)
        
        st.markdown("---")
        st.markdown("""
        ### ✨ Features
        - **Sections:** Hot Rolled (IPE, HEA, HEB, UB, UC) or Built-up with optional cap channels (UPN, PFC)
        - **Analysis:** Multi-crane support (1-3 cranes), automatic critical positioning
        - **Design:** ASD method per AISC 360-16 with Ω = 1.67 (flexure), 1.50 (shear)
        - **Checks:** Flexure, Shear, Web Yielding, Web Crippling, Deflection, Fatigue, Biaxial Bending
        - **Output:** Detailed calculations with code references, downloadable report
        """)


if __name__ == "__main__":
    main()
