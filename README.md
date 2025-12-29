# Runway Beam Design Tool

A web-based Python + Streamlit application for designing crane runway beams per AISC 360-16, Design Guide 7, and CMAA 70.

## Features

- **Complete AISC 360-16 Compliance**: All strength checks per the latest specification
- **Interactive Web Interface**: Easy-to-use Streamlit dashboard
- **Automatic Section Optimization**: Iteratively sizes section to meet all requirements
- **Visual Results**: Section drawings and utilization charts
- **Comprehensive Checks**:
  1. Major Axis Flexure (with LTB)
  2. Minor Axis Flexure
  3. Shear Strength
  4. Combined Forces Interaction
  5. Web Local Yielding
  6. Web Crippling
  7. Deflection Limits
  8. Fatigue Analysis

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

```bash
streamlit run runway_beam_app.py
```

The application will open in your default web browser at `http://localhost:8501`

## Input Parameters

The tool accepts the following inputs (matching the crane data sheet format):

### Crane Data
- Crane Capacity (MT)
- Bridge Span (m)
- Weight of Crane Bridge w/o Trolley (MT)
- Weight of Crab/Trolley (MT)
- Maximum Static Wheel Load (kN)
- Wheel Base (m)
- Number of Wheels per Rail

### Impact Factors
- Vertical Impact (%)
- Horizontal Impact (%)
- Longitudinal Impact (%)

### Runway Geometry
- Crane Beam Span (m)
- Lateral Unbraced Length (m)
- Rail Weight (kg/m)
- Rail Base Width (m)
- Rail Height (m)

### Material & Service
- Steel Grade (A36, A572 Gr.50, A992, A913 Gr.65)
- Crane Class (A through F per CMAA)
- Fatigue Category (A through F per AISC)

### Service Conditions
- Design Life (years)
- Operating Days per Year
- Operating Hours per Day
- Cycles per Hour

## Default Values (from provided data sheet)

| Parameter | Value | Unit |
|-----------|-------|------|
| Crane Capacity | 10 | MT |
| Bridge Span | 11.5 | M |
| Bridge Weight w/o Trolley | 3.31 | MT |
| Trolley Weight | 0.72 | MT |
| Max Static Wheel Load | 57.6 | kN |
| Wheel Base | 2.2 | M |
| Vertical Impact | 10 | % |
| Horizontal Impact | 20 | % |
| Longitudinal Impact | 10 | % |
| Beam Span | 4.5 | M |
| Lateral Unbraced Length | 4.5 | M |
| Rail Weight | 30 | kg/m |

## Output

The tool provides:
- Pass/Fail status for all design checks
- Utilization ratios for each check
- Recommended section dimensions
- Section properties (A, Ix, Iy, Sx, Zx, etc.)
- Visual section drawing
- Utilization bar chart
- Detailed calculation breakdown

## Code Standards

- **AISC 360-16**: Specification for Structural Steel Buildings
- **AISC Design Guide 7**: Industrial Buildings - Roofs to Anchor Rods
- **CMAA 70**: Specifications for Top Running Bridge and Gantry Type Multiple Girder Electric Overhead Traveling Cranes

## Files

- `runway_beam_app.py` - Main Streamlit application
- `runway_beam_design.py` - Core design module (standalone Python)
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Screenshots

When running, the application displays:
1. Input sidebar with all parameters
2. Design status banner (Pass/Fail)
3. Section geometry visualization
4. Utilization chart
5. Detailed results in tabbed sections

## License

For educational and professional engineering use.

## Notes

- Fatigue often governs runway beam design - this is normal for crane applications
- Conservative assumptions are used (e.g., Cb = 1.0 for moving loads)
- Rail restraint is not assumed by default (conservative approach)
- Built-up I-sections are generated; rolled shapes can be manually specified
