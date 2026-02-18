#!/usr/bin/env python3
"""
Single-file static site generator (no JS) supporting 4 modes:

  1) regular   : /{city}-{st}/
  2) cost      : regular + /cost/{city}-{st}/ (city-specific cost pages)
  3) state     : /{st}/ then /{st}/{city}/
  4) subdomain : each city is its own subdomain (links/canonicals become absolute)

Usage:
  python3 generate.py
  python3 -m http.server 8000 --directory public

ENV (optional):
  SITE_ORIGIN="https://example.com"          # used for absolute canonicals
  SUBDOMAIN_BASE="example.com"               # used for subdomain links/canonicals
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import csv
import html
import os
import sys
import re
import json
import shutil


# ============================================================
# US STATE NAMES (no dependency)
# ============================================================

US_STATE_NAMES: dict[str, str] = {
  "AL": "Alabama",
  "AK": "Alaska",
  "AZ": "Arizona",
  "AR": "Arkansas",
  "CA": "California",
  "CO": "Colorado",
  "CT": "Connecticut",
  "DE": "Delaware",
  "FL": "Florida",
  "GA": "Georgia",
  "HI": "Hawaii",
  "ID": "Idaho",
  "IL": "Illinois",
  "IN": "Indiana",
  "IA": "Iowa",
  "KS": "Kansas",
  "KY": "Kentucky",
  "LA": "Louisiana",
  "ME": "Maine",
  "MD": "Maryland",
  "MA": "Massachusetts",
  "MI": "Michigan",
  "MN": "Minnesota",
  "MS": "Mississippi",
  "MO": "Missouri",
  "MT": "Montana",
  "NE": "Nebraska",
  "NV": "Nevada",
  "NH": "New Hampshire",
  "NJ": "New Jersey",
  "NM": "New Mexico",
  "NY": "New York",
  "NC": "North Carolina",
  "ND": "North Dakota",
  "OH": "Ohio",
  "OK": "Oklahoma",
  "OR": "Oregon",
  "PA": "Pennsylvania",
  "RI": "Rhode Island",
  "SC": "South Carolina",
  "SD": "South Dakota",
  "TN": "Tennessee",
  "TX": "Texas",
  "UT": "Utah",
  "VT": "Vermont",
  "VA": "Virginia",
  "WA": "Washington",
  "WV": "West Virginia",
  "WI": "Wisconsin",
  "WY": "Wyoming",
  "DC": "District of Columbia",
}

FAVICON_FILES: tuple[str, ...] = (
  "favicon.ico",
  "favicon.svg",
  "favicon-16x16.png",
  "favicon-32x32.png",
  "apple-touch-icon.png",
)


# ============================================================
# CONFIG
# ============================================================

@dataclass(frozen=True)
class SiteConfig:
  # Data
  cities_csv: Path = Path("cities.csv")

  # Build / assets
  output_dir: Path = Path("public")
  image_filename: str = "man-servicing-koi-pond.webp"  # sits next to generate.py

  # Identity
  base_name: str = "Koi Pond Maintenance"
  brand_name: str = "Koi Pond Maintenance Company"

  # CTA
  cta_text: str = "Get Free Estimate"
  cta_href: str = "/contact/"

  # Pricing base
  cost_low: int = 600
  cost_high: int = 4500

  # Core titles/subs
  h1_title: str = "Koi Pond Maintenance and Cleaning Services"
  h1_short: str = "Koi Pond Maintenance Services"

  cost_title: str = "Koi Pond Maintenance Cost"

  howto_title: str = "How Koi Pond Maintenance Works"

  about_blurb: str = (
    "We provide professional koi pond maintenance services{loc} to keep ponds clean, balanced, and healthy for koi fish. "
    "Our service includes water quality management, debris removal, filtration checks, and routine pond care. "
    "Get reliable koi pond service from a local maintenance professional."
  )

  main_h2: tuple[str, ...] = (
    "What Does Professional Koi Pond Maintenance Include?",
    "How Often Does a Koi Pond Need Maintenance?",
    "Why Is My Koi Pond Water Cloudy or Green?",
    "Why Is Foam Forming on the Surface of My Koi Pond?",
    "How Do You Remove Sludge or Muck From the Bottom of a Koi Pond?",
    "Why Is There So Much Algae in My Koi Pond?"
  )


  main_p: tuple[str, ...] = (
    "Professional koi pond maintenance includes cleaning debris, managing algae, checking filtration systems, and maintaining proper water quality. These services help keep koi healthy while preventing buildup that can damage the pond ecosystem.",
    "Most koi ponds need maintenance every two to four weeks, with more frequent service during warmer months when waste and algae increase. The exact schedule depends on pond size, fish load, filtration capacity, and seasonal conditions.",
    "Koi pond water often turns cloudy or green due to excess algae, poor filtration, or imbalanced water chemistry. Regular maintenance helps control algae growth and keeps water clear and safe for fish.",
    "Foam forms on the surface of a koi pond when excess proteins from fish waste, uneaten food, and decaying organic matter accumulate in the water. This usually indicates poor water quality or filtration that is no longer keeping up with the pond’s biological load.",
    "Sludge or muck is removed from the bottom of a koi pond using controlled vacuuming and targeted cleaning that lifts settled waste without disturbing fish or beneficial bacteria. Proper sludge removal improves oxygen levels, reduces nutrient buildup, and helps prevent recurring algae and foul odors.",
    "Excess algae in a koi pond is usually caused by high nutrient levels, sunlight exposure, and insufficient filtration. Without consistent maintenance, algae can grow rapidly and overwhelm the pond ecosystem."
  )

  # LOCAL COST
  location_cost_h2: str = "How Much Does Koi Pond Maintenance Cost{loc}?"

  location_cost_p: str = (
    "Koi pond maintenance costs{loc} typically range between {cost_lo} and {cost_hi} per year, "
    "depending on pond size, service frequency, filtration complexity, and fish load. "
    "Pricing can also vary based on seasonal needs and local labor rates."
  )

  # Meta descriptions (keep them unique per page, ~150-160 chars)
  home_description: str = (
    "Professional koi pond maintenance to keep water clean, balanced, and healthy for koi fish. Routine cleaning and pond care available."
  )

  city_description: str = (
    "Koi pond maintenance services{loc}. Water quality management, cleaning, and filtration care for healthy koi ponds."
  )

  cost_description: str = (
    "Koi pond maintenance cost guide: typical pricing ranges, service frequency options, and factors that affect total cost."
  )

  cost_city_description: str = (
    "Koi pond maintenance cost{loc}: typical local pricing ranges and factors like pond size, filtration, and service schedule."
  )

  howto_description: str = (
    "How koi pond maintenance works: an overview of cleaning, water quality control, algae management, and filtration care."
  )

  contact_description: str = (
    "Request a quote for professional koi pond maintenance. Share your location and pond details to get pricing and scheduling."
  )

  state_description: str = (
    "Koi pond maintenance services{loc}. Browse cities we serve, view typical pricing ranges, and request a quote."
  )




  cost_body = """
  <section>
    <h2>Scoreboard Repair & Installation Cost Ranges (Most Common Scenarios)</h2>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Service Scenario</th>
            <th>Typical Cost Range</th>
            <th>What You’re Paying For</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Minor scoreboard repair (loose wiring, fuse, simple fault)</td>
            <td>$150–$500</td>
            <td>Troubleshooting, minor electrical repair, testing</td>
          </tr>
          <tr>
            <td>Scoreboard control or power issue repair</td>
            <td>$300–$1,000</td>
            <td>Controller diagnostics, power supply repair or replacement</td>
          </tr>
          <tr>
            <td>LED module or digit replacement</td>
            <td>$500–$2,500</td>
            <td>Parts replacement, wiring, calibration</td>
          </tr>
          <tr>
            <td>Refurbish older scoreboard (multiple components)</td>
            <td>$1,500–$5,000+</td>
            <td>Multiple repairs, parts sourcing, extended labor</td>
          </tr>
          <tr>
            <td>Install new wall-mounted indoor scoreboard</td>
            <td>$1,000–$4,000</td>
            <td>Mounting, electrical hookup, setup and testing</td>
          </tr>
          <tr>
            <td>Install large outdoor or stadium scoreboard</td>
            <td>$3,000–$15,000+</td>
            <td>Structural mounting, electrical work, lift access, commissioning</td>
          </tr>
          <tr>
            <td>High-access work (lift, crane, or tall gym wall)</td>
            <td>+20% to +60%</td>
            <td>Equipment rental, safety setup, extra labor</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p>
      <strong>Typical total:</strong> $300–$2,500 for common scoreboard repairs.
      <strong>Large installs or major refurbishments:</strong> $5,000–$15,000+ is common.
    </p>

    <hr />

    <h2>Cost by Severity (Fast Self-Assessment)</h2>

    <h3>Minor</h3>
    <ul>
      <li><strong>What it looks like:</strong> scoreboard powers on but has display errors or intermittent issues</li>
      <li><strong>Expected cost:</strong> $150–$500</li>
      <li><strong>Common work:</strong> wiring fixes, fuse replacement, basic diagnostics</li>
    </ul>

    <h3>Moderate</h3>
    <ul>
      <li><strong>What it looks like:</strong> dead sections, failed digits, controller problems</li>
      <li><strong>Expected cost:</strong> $500–$2,500</li>
      <li><strong>Common work:</strong> LED module replacement, control board repair</li>
    </ul>

    <h3>Severe</h3>
    <ul>
      <li><strong>What it looks like:</strong> widespread failure, outdated system, structural or power issues</li>
      <li><strong>Expected cost:</strong> $2,500–$15,000+</li>
      <li><strong>Common work:</strong> major refurbishment or full scoreboard installation</li>
    </ul>

    <hr />

    <h2>Repair & Installation Cost by Scoreboard Type</h2>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Scoreboard Type</th>
            <th>Typical Cost Range</th>
            <th>Why It Costs More (or Less)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Small indoor gym scoreboard</td>
            <td>$300–$3,000</td>
            <td>Easier access, simpler mounting and wiring</td>
          </tr>
          <tr>
            <td>Wall-mounted school scoreboard</td>
            <td>$500–$6,000</td>
            <td>Height access and electrical routing</td>
          </tr>
          <tr>
            <td>Outdoor field scoreboard</td>
            <td>$1,500–$10,000+</td>
            <td>Weatherproofing, structural supports, trenching</td>
          </tr>
          <tr>
            <td>Stadium / multi-sport scoreboard</td>
            <td>$5,000–$25,000+</td>
            <td>Large structures, advanced electronics, lifts or cranes</td>
          </tr>
        </tbody>
      </table>
    </div>

    <hr />

    <h2>What Increases Scoreboard Repair or Installation Cost</h2>

    <ul>
      <li><strong>Height and access:</strong> lifts, scaffolding, or cranes significantly increase cost</li>
      <li><strong>Electrical issues:</strong> outdated wiring or code upgrades add labor</li>
      <li><strong>Part availability:</strong> older scoreboards may need custom or discontinued parts</li>
      <li><strong>Outdoor exposure:</strong> weather damage increases repair scope</li>
      <li><strong>Structural work:</strong> damaged mounts or supports require rebuilding</li>
      <li><strong>Permits and inspections:</strong> sometimes required for new installations</li>
    </ul>

    <hr />

    <h2>When Repair Is Enough vs When Replacement Makes More Sense</h2>

    <h3>Repair is usually enough if:</h3>
    <ul>
      <li>The scoreboard structure is sound</li>
      <li>Failures are limited to wiring, power, or individual display components</li>
      <li>Replacement parts are still available</li>
    </ul>

    <h3>Replacement or full installation is usually required if:</h3>
    <ul>
      <li>Multiple sections have failed or are obsolete</li>
      <li>Parts are discontinued or incompatible</li>
      <li>The scoreboard no longer meets league or visibility requirements</li>
      <li>Structural or mounting damage is present</li>
    </ul>

    <p>
      <strong>Rule:</strong> If repair costs exceed 50% of a new scoreboard, replacement is usually the better long-term option.
    </p>

    <hr />

    <h2>Common Add-Ons and Related Costs</h2>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Add-On</th>
            <th>Typical Cost</th>
            <th>Best Use</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>New scoreboard controller</td>
            <td>$300–$2,000</td>
            <td>Improves reliability and compatibility</td>
          </tr>
          <tr>
            <td>Wireless control system</td>
            <td>$500–$3,000</td>
            <td>Easier operation from sidelines or booths</td>
          </tr>
          <tr>
            <td>Protective enclosures or weather shielding</td>
            <td>$300–$2,500</td>
            <td>Extends lifespan of outdoor scoreboards</td>
          </tr>
          <tr>
            <td>Lift or crane rental</td>
            <td>$500–$3,500+</td>
            <td>Required for high or large installations</td>
          </tr>
        </tbody>
      </table>
    </div>

    <hr />

    <h2>What a Scoreboard Repair or Installation Quote Should Include</h2>

    <ul>
      <li>Repair vs replacement scope</li>
      <li>Scoreboard size, type, and mounting height</li>
      <li>Electrical work included or excluded</li>
      <li>Access method (lift, scaffold, crane)</li>
      <li>Parts sourcing and warranty details</li>
      <li>Permits, inspections, and code compliance if required</li>
    </ul>

    <hr />

    <h2>Insurance, School, and Municipal Considerations</h2>

    <p>
      Scoreboard repairs may be covered if damage is caused by a sudden event (storm, impact).
      New installations are typically capital improvements and not insurance claims.
      Schools and municipalities often require permits and licensed contractors.
    </p>
  </section>
  """


  howto_body = """
  <section>
    <p>
      Installing a scoreboard requires more than simply mounting a display. Proper planning, structural support, and electrical preparation are critical to ensure safety, reliability, and long-term performance. This guide explains how to install a scoreboard step by step, covering site planning, power and data requirements, mounting methods, and final commissioning for indoor and outdoor installations.
    </p>


    <h2>Step 1: Plan the Scoreboard Installation</h2>

    <p>
      Proper planning prevents structural failures, electrical issues, and costly rework.
    </p>

    <h3>Confirm the Installation Location</h3>
    <ul>
      <li>Wall-mounted, pole-mounted, or freestanding structure</li>
      <li>Clear visibility from primary seating areas</li>
      <li>Compliance with local height and setback requirements</li>
    </ul>

    <h3>Verify Structural Support</h3>
    <ul>
      <li>Concrete footing or structural steel for pole-mounted units</li>
      <li>Load-rated framing for wall-mounted scoreboards</li>
      <li>Wind load and vibration resistance for outdoor installations</li>
    </ul>

    <p>
      Scoreboards are heavy and act as wind sails. Mounting to non-structural framing is unsafe.
    </p>

    <hr />

    <h2>Step 2: Prepare Electrical and Data Connections</h2>

    <p>
      Most modern scoreboards require dedicated power and low-voltage control wiring.
    </p>

    <h3>Electrical Requirements</h3>
    <ul>
      <li>Dedicated circuit sized per manufacturer specifications</li>
      <li>Weather-rated disconnect for outdoor installations</li>
      <li>Proper grounding and surge protection</li>
    </ul>

    <h3>Control and Data Cabling</h3>
    <ul>
      <li>Ethernet, fiber, or proprietary control cable</li>
      <li>Conduit installed before mounting the scoreboard</li>
      <li>Control location planned for clear sightlines</li>
    </ul>

    <p>
      Electrical work typically requires a licensed electrician and local inspection approval.
    </p>

    <hr />

    <h2>Step 3: Mount the Scoreboard Structure</h2>

    <h3>Wall-Mounted Scoreboards</h3>
    <ol>
      <li>Locate and mark structural attachment points</li>
      <li>Install mounting brackets or rails per manufacturer layout</li>
      <li>Verify level and plumb before final tightening</li>
    </ol>

    <h3>Pole-Mounted or Freestanding Scoreboards</h3>
    <ol>
      <li>Set concrete footings to required depth and cure fully</li>
      <li>Anchor steel poles or frames using rated hardware</li>
      <li>Confirm vertical alignment before mounting the display</li>
    </ol>

    <p>
      Never attempt to lift or mount a scoreboard without proper lifting equipment and crew support.
    </p>

    <hr />

    <h2>Step 4: Install the Scoreboard Display</h2>

    <ol>
      <li>Lift the scoreboard into position using a crane or lift</li>
      <li>Secure the display to the mounting frame</li>
      <li>Connect power, grounding, and control wiring</li>
      <li>Seal all exterior penetrations</li>
    </ol>

    <p>
      Outdoor scoreboards must be fully weather-sealed to prevent moisture intrusion.
    </p>

    <hr />

    <h2>Step 5: Test, Configure, and Commission</h2>

    <ul>
      <li>Power on and verify display operation</li>
      <li>Test scoring, timing, and auxiliary functions</li>
      <li>Configure software and control interfaces</li>
      <li>Train operators on basic use and shutdown procedures</li>
    </ul>

    <p>
      Final testing ensures the scoreboard operates reliably during live events.
    </p>
  </section>

  """


CONFIG = SiteConfig()
CityWithCol = tuple[str, str, float]


# ============================================================
# LOAD CITIES
# ============================================================

def load_cities_from_csv(path: Path) -> tuple[CityWithCol, ...]:
  out: list[CityWithCol] = []
  with path.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    required = {"city", "state", "col"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
      raise ValueError(f"CSV must have headers: city,state,col (found: {reader.fieldnames})")

    for i, row in enumerate(reader, start=2):
      city = (row.get("city") or "").strip()
      state = (row.get("state") or "").strip().upper()
      col_raw = (row.get("col") or "").strip()
      if not city or not state or not col_raw:
        raise ValueError(f"Missing city/state/col at CSV line {i}: {row}")
      try:
        col = float(col_raw)
      except ValueError as e:
        raise ValueError(f"Invalid col at CSV line {i}: {col_raw!r}") from e
      out.append((city, state, col))
  return tuple(out)


CITIES: tuple[CityWithCol, ...] = load_cities_from_csv(CONFIG.cities_csv)

def generate_state_to_col_map():
  total_state_cols = {}
  for _, st, col in CITIES:
    if st in total_state_cols:
      total_state_cols[st].append(col)
    else:
      total_state_cols[st] = [col]
  
  state_col_map = {}
  for st, cols in total_state_cols.items():
    state_col_map[st] = sum(cols) / len(cols)
  
  return state_col_map

STATE_TO_COL_MAP = generate_state_to_col_map()



# ============================================================
# HELPERS
# ============================================================

def esc(s: str) -> str:
  return html.escape(s, quote=True)

def slugify(s: str) -> str:
  s = s.strip().lower()
  s = re.sub(r"&", " and ", s)
  s = re.sub(r"[^a-z0-9]+", "-", s)
  s = re.sub(r"-{2,}", "-", s).strip("-")
  return s

def cost_slug() -> str:
  return slugify(CONFIG.cost_title)

def howto_slug() -> str:
  return slugify(CONFIG.howto_title)

def filename_to_alt(filename: str) -> str:
  if not filename:
    return ""
  alt = filename.lower()
  alt = re.sub(r"\.[a-z0-9]+$", "", alt)
  alt = re.sub(r"[-_]+", " ", alt)
  alt = re.sub(r"\b\d+\b", "", alt)
  alt = re.sub(r"\s+", " ", alt).strip()
  return alt.capitalize()

def clamp_title(title: str, max_chars: int = 70) -> str:
  if len(title) <= max_chars:
    return title
  return title[: max_chars - 1].rstrip() + "…"

def state_full(abbr: str) -> str:
  return US_STATE_NAMES.get(abbr.upper(), abbr.upper())

def write_text(path: Path, content: str) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(content, encoding="utf-8")

def reset_output_dir(p: Path) -> None:
  if p.exists():
    shutil.rmtree(p)
  p.mkdir(parents=True, exist_ok=True)

def copy_site_image(*, src_dir: Path, out_dir: Path, filename: str) -> None:
  src = src_dir / filename
  if not src.exists():
    raise FileNotFoundError(f"Missing image next to generate.py: {src}")
  shutil.copyfile(src, out_dir / filename)

def copy_static_files(*, src_dir: Path, out_dir: Path, filenames: tuple[str, ...]) -> None:
  for name in filenames:
    src = src_dir / name
    if not src.exists():
      raise FileNotFoundError(f"Missing static file: {src}")
    shutil.copyfile(src, out_dir / name)

def cities_by_state(cities: tuple[CityWithCol, ...]) -> dict[str, list[CityWithCol]]:
  m: dict[str, list[CityWithCol]] = {}
  for city, st, col in cities:
    m.setdefault(st, []).append((city, st, col))
  for st in m:
    m[st].sort(key=lambda t: t[0].lower())
  return m

def linkify_curly(text: str, *, home_href: str) -> str:
  """
  Replace {text} with a link to the home page.
  """
  parts: list[str] = []
  last = 0
  for m in re.finditer(r"\{([^}]+)\}", text):
    parts.append(esc(text[last:m.start()]))
    parts.append(f'<a href="{esc(home_href)}">{esc(m.group(1))}</a>')
    last = m.end()
  parts.append(esc(text[last:]))
  return "".join(parts)

def city_subdomain_slug(*, city: str, st: str):
  return f"{city}{st}".lower().replace(" ", "")



# ============================================================
# MODE + URLS
# ============================================================

Mode = str  # "regular" | "cost" | "state" | "subdomain" | "regular_city_only"

CLI_SITE_ORIGIN = sys.argv[2] if len(sys.argv) > 2 else ""
SITE_ORIGIN = (CLI_SITE_ORIGIN or os.environ.get("SITE_ORIGIN") or "").rstrip("/")
SUBDOMAIN_BASE = (os.environ.get("SUBDOMAIN_BASE") or "").strip().lower().strip(".")


# ============================================================
# FEATURE FLAGS PER MODE
# ============================================================

MODE_FEATURES: dict[str, dict[str, bool]] = {
  "regular": {"cost": True, "howto": True, "contact": True},
  "cost": {"cost": True, "howto": False, "contact": True},
  "state": {"cost": False, "howto": False, "contact": True},
  "subdomain": {"cost": False, "howto": False, "contact": True},
  "regular_city_only": {"cost": False, "howto": False, "contact": True},
}

def feature(mode: Mode, key: str) -> bool:
  return MODE_FEATURES.get(mode, MODE_FEATURES["regular"]).get(key, False)


# ============================================================
# COPY VARIANTS (1..5) selected by mode (override with env)
# (kept for compatibility; not used in this file)
# ============================================================

COPY_VARIANT_BY_MODE: dict[str, int] = {
  "regular": 1,
  "cost": 2,
  "state": 3,
  "subdomain": 4,
  "regular_city_only": 5,
}

def resolve_copy_idx(mode: str) -> int:
  """
  Returns idx 0..4 for picking the copy variant.
  Env override: COPY_VARIANT=1..5
  Otherwise uses COPY_VARIANT_BY_MODE[mode].
  """
  raw = (os.environ.get("COPY_VARIANT") or "").strip()
  if raw.isdigit():
    v = int(raw)
  else:
    v = COPY_VARIANT_BY_MODE.get(mode, 1)

  v = max(1, min(5, v))  # clamp 1..5
  return v - 1           # idx 0..4


def rel_city_path_regular(city: str, st: str) -> str:
  return f"/{slugify(city)}-{slugify(st)}/"

def rel_city_path_state(city: str, st: str) -> str:
  return f"/{slugify(st)}/{slugify(city)}/"

def abs_city_origin_subdomain(slug: str) -> str:
  base = SUBDOMAIN_BASE or (
    SITE_ORIGIN.replace("https://", "").replace("http://", "").split("/")[0]
    if SITE_ORIGIN else ""
  )
  if not base:
    return f"/{slug}/"
  return f"https://{slug}.{base}/"

def href_home(mode: Mode) -> str:
  return "/"

def href_city(mode: Mode, city: str, st: str) -> str:
  if mode == "state":
    return rel_city_path_state(city, st)
  if mode == "subdomain":
    slug = city_subdomain_slug(city=city, st=st)
    return abs_city_origin_subdomain(slug)
  return rel_city_path_regular(city, st)

def href_state(mode: Mode, st: str) -> str:
  return f"/{slugify(st)}/"

def href_cost_index(mode: Mode) -> str:
  p = f"/{cost_slug()}/"
  return (SITE_ORIGIN + p) if (mode == "subdomain" and SITE_ORIGIN) else p

def href_howto_index(mode: Mode) -> str:
  p = f"/{howto_slug()}/"
  return (SITE_ORIGIN + p) if (mode == "subdomain" and SITE_ORIGIN) else p

def href_contact(mode: Mode) -> str:
  return "/contact/"

def canonical_for(mode: Mode, path_or_abs: str) -> str:
  if path_or_abs.startswith("http://") or path_or_abs.startswith("https://"):
    return path_or_abs
  if SITE_ORIGIN:
    return SITE_ORIGIN + path_or_abs
  return path_or_abs


# ============================================================
# THEME (small but complete)
# ============================================================

CSS = """
:root{
  --bg:#fafaf9; --surface:#fff; --ink:#111827; --muted:#4b5563; --line:#e7e5e4; --soft:#f5f5f4;
  --cta:#158940; --cta2:#147a38; --max:980px; --radius:16px;
  --shadow:0 10px 30px rgba(17,24,39,.06); --shadow2:0 10px 24px rgba(17,24,39,.08);
}
*{box-sizing:border-box}
html,body{max-width:100%;overflow-x:clip;}
body{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;color:var(--ink);background:var(--bg);line-height:1.6}
a{color:inherit}
.topbar{position:sticky;top:0;z-index:50;background:rgba(250,250,249,.92);backdrop-filter:saturate(140%) blur(10px);border-bottom:1px solid var(--line)}
.topbar-inner{max-width:var(--max);margin:0 auto;padding:12px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px}
.brand{font-weight:900;letter-spacing:-.02em;text-decoration:none}
.brand-wrap{display:flex;align-items:center;gap:8px}
.brand-logo{display:block;width:22px;height:22px;flex-shrink:0}
.nav{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}
.nav a:not(.btn){text-decoration:none;font-size:13px;color:var(--muted);padding:7px 10px;border-radius:12px;border:1px solid transparent}
.nav a:not(.btn):hover{background:var(--soft);border-color:var(--line)}
.nav a:not(.btn)[aria-current="page"]{color:var(--ink);background:var(--soft);border:1px solid var(--line)}
.btn{display:inline-block;padding:9px 12px;background:var(--cta);color:#fff;border-radius:12px;text-decoration:none;font-weight:900;font-size:13px;border:1px solid rgba(0,0,0,.04);box-shadow:0 8px 18px rgba(22,163,74,.18)}
.btn:hover{background:var(--cta2)}
header{border-bottom:1px solid var(--line);background:radial-gradient(1200px 380px at 10% -20%, rgba(22,163,74,.08), transparent 55%),radial-gradient(900px 320px at 95% -25%, rgba(17,24,39,.06), transparent 50%),#fbfbfa}
.hero{max-width:var(--max);margin:0 auto;padding:34px 18px 24px;display:grid;gap:10px}
.hero h1{margin:0;font-size:30px;letter-spacing:-.03em;line-height:1.18}
.sub{margin:0;color:var(--muted);max-width:78ch;font-size:14px}
main{max-width:var(--max);margin:0 auto;padding:22px 18px 46px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);max-width:100%}
.img{margin-top:14px;margin-bottom:16px;border-radius:14px;overflow:hidden;border:1px solid var(--line);background:var(--soft);box-shadow:var(--shadow2);width:100%}
.img img{display:block;width:100%;height:auto}
@media (min-width:900px){.img{max-width:50%;margin-left:auto;margin-right:auto}}
h2{margin:18px 0 8px;font-size:16px;letter-spacing:-.01em}
p{margin:0 0 10px}
.muted{color:var(--muted);font-size:13px}
hr{border:0;border-top:1px solid var(--line);margin:18px 0}
.city-grid{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.city-grid a{display:block;text-decoration:none;color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px;font-weight:800;font-size:14px;box-shadow:0 10px 24px rgba(17,24,39,.05)}
.city-grid a:hover{transform:translateY(-1px);box-shadow:0 14px 28px rgba(17,24,39,.08)}
footer{border-top:1px solid var(--line);background:#fbfbfa}
.footer-inner{max-width:var(--max);margin:0 auto;padding:28px 18px;display:grid;gap:10px}
.footer-links{display:flex;gap:12px;flex-wrap:wrap}
.footer-links a{color:var(--muted);text-decoration:none;font-size:13px}
.small{color:var(--muted);font-size:12px}

/* ---------- TABLES (base look) ---------- */
table{width:100%;border-collapse:separate;border-spacing:0;margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:14px}
thead th{background:var(--soft);color:var(--ink);font-size:13px;text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:10px 12px;vertical-align:top;border-bottom:1px solid var(--line);font-size:14px;color:var(--ink)}
tbody tr:last-child td{border-bottom:none}

/* wrapper that scrolls (only works if you wrap tables in .table-scroll) */
.table-scroll{max-width:100%}

@media (max-width:640px){
  .topbar-inner{flex-direction:column;align-items:stretch;gap:10px}
  .nav{justify-content:center}
  .nav .btn{width:100%;text-align:center}

  /* ✅ CENTER BRAND ON MOBILE */
  .topbar-inner .brand-wrap{
    justify-content:center;
  }
  .topbar-inner .brand-wrap span{
    text-align:center;
  }

  /* only the wrapper scrolls, NOT the whole page */
  .table-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
  .table-scroll table{min-width:720px}
}

/* -----------------------
   CONTACT FORM (match first block)
----------------------- */
.form-grid{
  margin-top:14px;
  display:grid;
  gap:14px;
  grid-template-columns:1fr 320px;
  align-items:start;
}
@media (max-width: 900px){
  .form-grid{grid-template-columns:1fr}
}

.embed-card{
  border:1px solid var(--line);
  border-radius:14px;
  padding:18px;
  background:var(--soft);
}

.nx-center{
  display:flex;
  justify-content:center; /* keep the small iframe centered */
}

/* Keep Networx at the required embedded size */
#nx_form{
  width:242px;
  height:375px;
}

/* Force iframe to fill the fixed-size container */
#networx_form_container iframe{
  width:100% !important;
  height:100% !important;
  border:0 !important;
}

/* -----------------------
   WHY BOX (match first block)
----------------------- */
.why-box{
  background:#fff;
  border:1px solid var(--line);
  border-radius:14px;
  padding:14px;
  box-shadow:0 10px 24px rgba(17,24,39,0.05);
}
.why-box h3{
  margin:0 0 10px;
  font-size:15px;
}
.why-list{
  list-style:none;
  padding:0;
  margin:0;
  display:grid;
  gap:10px;
}
.why-item{
  display:flex;
  gap:10px;
  align-items:flex-start;
  color:var(--muted);
  font-size:13px;
}
.tick{
  width:18px;
  height:18px;
  border-radius:999px;
  background:rgba(22,163,74,0.12);
  border:1px solid rgba(22,163,74,0.22);
  display:inline-flex;
  align-items:center;
  justify-content:center;
}
.tick:before{
  content:"✓";
  font-weight:900;
  font-size:12px;
}
""".strip()


# ============================================================
# HTML PRIMITIVES
# ============================================================

def nav_html(
  *,
  mode: Mode,
  current: str,
  show_cost: bool = True,
  show_howto: bool = True,
  show_contact: bool = True,
) -> str:
  def item(href: str, label: str, key: str) -> str:
    cur = ' aria-current="page"' if current == key else ""
    return f'<a href="{esc(href)}"{cur}>{esc(label)}</a>'

  parts: list[str] = []
  parts.append(item(href_home(mode), "Home", "home"))

  if show_cost:
    parts.append(item(href_cost_index(mode), "Cost", "cost"))
  if show_howto:
    parts.append(item(href_howto_index(mode), "How-To", "howto"))

  if show_contact:
    parts.append(f'<a class="btn" href="{esc(href_contact(mode))}">{esc(CONFIG.cta_text)}</a>')

  return '<nav class="nav" aria-label="Primary navigation">' + "".join(parts) + "</nav>"


def base_html(
  *,
  mode: Mode,
  title: str,
  canonical: str,
  current_nav: str,
  body: str,
  description: str = CONFIG.h1_title,
  nav_show_cost: bool = True,
  nav_show_howto: bool = True,
  nav_show_contact: bool = True,
) -> str:
  return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}" />
  <link rel="canonical" href="{esc(canonical_for(mode, canonical))}" />
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <meta name="apple-mobile-web-app-title" content="{esc(CONFIG.brand_name)}">
  <style>
{CSS}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <a class="brand brand-wrap" href="{esc(href_home(mode))}">
        <img
          src="/favicon-32x32.png"
          alt=""
          class="brand-logo"
          width="20"
          height="20"
          loading="eager"
          decoding="async"
        />
        <span>{esc(CONFIG.brand_name)}</span>
      </a>
      {nav_html(mode=mode, current=current_nav, show_cost=nav_show_cost, show_howto=nav_show_howto, show_contact=nav_show_contact)}
    </div>
  </div>
{body}
</body>
</html>
"""


def header_block(*, h1: str) -> str:
  return f"""
<header>
  <div class="hero">
    <h1>{esc(h1)}</h1>
  </div>
</header>
""".rstrip()


def footer_block(*, mode: Mode, show_cta: bool = True, show_cost: bool = True, show_howto: bool = True) -> str:
  cta_html = ""
  if show_cta:
    cta_html = f"""
    <p class="sub">Ready to move forward? Request a free estimate.</p>
    <div>
      <a class="btn" href="{esc(href_contact(mode))}">{esc(CONFIG.cta_text)}</a>
    </div>
""".rstrip()

  links: list[str] = [f'<a href="{esc(href_home(mode))}">Home</a>']
  if show_cost:
    links.append(f'<a href="{esc(href_cost_index(mode))}">Cost</a>')
  if show_howto:
    links.append(f'<a href="{esc(href_howto_index(mode))}">How-To</a>')

  return f"""
<footer>
  <div class="footer-inner">
    {cta_html}
    <div class="small">© {esc(CONFIG.brand_name)}. All rights reserved.</div>
  </div>
</footer>
""".rstrip()


def page_shell(
  *,
  h1: str,
  inner_html: str,
  show_image: bool,
  show_footer_cta: bool,
  mode: Mode,
  footer_show_cost: bool = True,
  footer_show_howto: bool = True,
) -> str:
  img_src = f"/{CONFIG.image_filename}"
  img_alt = filename_to_alt(CONFIG.image_filename)
  img_html = ""
  if show_image:
    img_html = f"""
    <div class="img">
      <img src="{img_src}" alt="{img_alt}" width="600" height="900" fetchpriority="high" loading="eager" />
    </div>
""".rstrip()

  return (
    header_block(h1=h1)
    + f"""
<main>
  <section class="card">
{img_html}
    {inner_html}
  </section>
</main>
"""
    + footer_block(mode=mode, show_cta=show_footer_cta, show_cost=footer_show_cost, show_howto=footer_show_howto)
  ).rstrip()


def make_page(
  *,
  mode: Mode,
  h1: str,
  canonical: str,
  nav_key: str,
  inner: str,
  description: str = CONFIG.h1_title,
  show_image: bool = True,
  show_footer_cta: bool = True,
  nav_show_cost: bool = True,
  nav_show_howto: bool = True,
  nav_show_contact: bool = True,
  footer_show_cost: bool = True,
  footer_show_howto: bool = True,
) -> str:
  h1 = clamp_title(h1, 70)
  title = h1  # enforce title == h1

  return base_html(
    mode=mode,
    title=title,
    canonical=canonical,
    current_nav=nav_key,
    description=description,
    nav_show_cost=nav_show_cost,
    nav_show_howto=nav_show_howto,
    nav_show_contact=nav_show_contact,
    body=page_shell(
      h1=h1,
      inner_html=inner,
      show_image=show_image,
      show_footer_cta=show_footer_cta,
      mode=mode,
      footer_show_cost=footer_show_cost,
      footer_show_howto=footer_show_howto,
    ),
  )


def make_section(*, headings: tuple[str, ...], paras: tuple[str, ...]) -> str:
  parts: list[str] = []
  for h2, p in zip(headings, paras):
    parts.append(f"<h2>{esc(h2)}</h2>")
    parts.append(f"<p>{esc(p)}</p>")
  return "\n".join(parts)


def location_cost_section(city: str = "", st: str = "", col: float = 1) -> str:
  rep = (
    f" in {city}, {st}"
    if city and st
    else f" in {st}"
    if st
    else ""
  )
  cost_lo = f"<strong>${int(CONFIG.cost_low * col)}</strong>"
  cost_hi = f"<strong>${int(CONFIG.cost_high * col)}</strong>"

  h2 = CONFIG.location_cost_h2.replace("{loc}", rep)
  p = (
    CONFIG.location_cost_p
    .replace("{loc}", rep)
    .replace("{cost_lo}", cost_lo)
    .replace("{cost_hi}", cost_hi)
  )
  return f"<h2>{esc(h2)}</h2>\n<p>{p}</p>"

def about_section(city: str = "", st: str = "") -> str:
  rep = (
    f" in {city}, {st}"
    if city and st
    else f" in {st}"
    if st
    else " nationwide"
  )

  p = CONFIG.about_blurb.replace("{loc}", rep)

  return f"<p>{p}</p>"

def clean_meta_description(*, content, city: str = "", st: str = "") -> str:
  rep = (
    f" in {city}, {st}"
    if city and st
    else f" in {st}"
    if st
    else ""
  )

  return content.replace("{loc}", rep)



# ============================================================
# PAGE BODY SNIPPETS (simple defaults)
# ============================================================


# ============================================================
# PAGE CONTENT FACTORIES
# ============================================================

def homepage_html(*, mode: Mode) -> str:
  # Base content (always shown)
  inner = (
    about_section()
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section()
  )

  # Only show city index when NOT in subdomain mode
  if mode != "subdomain":
    links = "\n".join(
      f'<li><a href="{esc(href_city(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
      for c, s, _ in CITIES
    )

    inner += (
      """
<hr />
<h2>Our Service Area</h2>
<p class="muted">We provide services nationwide, including in the following cities:</p>
<ul class="city-grid">
"""
      + links
      + """
</ul>
"""
    )


  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  description = clean_meta_description(content=CONFIG.home_description)

  return make_page(
    mode=mode,
    h1=CONFIG.h1_title,
    canonical="/",
    nav_key="home",
    inner=inner,
    description=description,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def contact_page_html(mode: Mod, canonical: str = "/contact/") -> str:
  h1 = "Request a Free Estimate"
  sub = "All you have to do is fill out the form below."

  why_title = "Why Our Service Works"
  why_bullets = (
    "You receive a free estimate up front, with no obligation",
    "Each request is reviewed by an experienced professional",
    "Coverage is available in most U.S. locations",
    "Requests are handled promptly to keep projects moving",
  )

  why_items = "\n".join(
    f'<li class="why-item"><span class="tick" aria-hidden="true"></span><span>{esc(t)}</span></li>'
    for t in why_bullets
  )

  networx_embed = """
<div id="networx_form_container" style="margin:0px;padding:0px;">
    <div id = "nx_form" style = "width: 242px; height: 375px;">
        <script type="text/javascript" src = "https://api.networx.com/iframe.php?aff_id=73601bc3bd5a961a61a973e92e29f169&aff_to_form_id=8028"></script>
    </div>
</div>
""".strip()

  inner = f"""
<div class="form-grid">
  <div class="embed-card">
    <div class="nx-center">
      {networx_embed}
    </div>
  </div>

  <aside class="why-box" aria-label="Why choose us">
    <h3>{esc(why_title)}</h3>
    <ul class="why-list">
      {why_items}
    </ul>
  </aside>
</div>
""".strip()

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  description = clean_meta_description(content=CONFIG.contact_description)

  return make_page(
    mode=mode,
    h1=h1,
    canonical=canonical,
    nav_key="contact",
    inner=inner,
    description=description,
    show_image=False,
    show_footer_cta=False,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def city_page_html(*, mode: Mode, city: str, st: str, col: float, canonical: str) -> str:
  inner = (
    about_section(city=city, st=st)
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section(city, st, col)
  )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  description = clean_meta_description(content=CONFIG.city_description, city=city, st=st)

  return make_page(
    mode=mode,
    h1=clamp_title(f"{CONFIG.h1_short} in {city}, {st}", 70),
    canonical=canonical,
    nav_key="home",
    inner=inner,
    description=description,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def cost_page_html(*, mode: Mode, include_city_index: bool) -> str:
  inner = CONFIG.cost_body

  if include_city_index:
    links = "\n".join(
      f'<li><a href="{esc(cost_city_href(mode, c, s))}">{esc(c)}, {esc(s)}</a></li>'
      for c, s, _ in CITIES
    )
    inner += (
      """
<hr />
<h2>Our Service Area</h2>
<p class="muted">See local price ranges by city:</p>
<ul class="city-grid">
"""
      + links
      + """
</ul>
"""
    )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  description = clean_meta_description(content=CONFIG.cost_description)

  return make_page(
    mode=mode,
    h1=CONFIG.cost_title,
    canonical=f"/{cost_slug()}/",
    nav_key="cost",
    inner=inner,
    description=description,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def cost_city_href(mode: Mode, city: str, st: str) -> str:
  if mode == "subdomain" and SITE_ORIGIN:
    return SITE_ORIGIN + f"/cost/{slugify(city)}-{slugify(st)}/"
  return f"/cost/{slugify(city)}-{slugify(st)}/"


def cost_city_page_html(*, mode: Mode, city: str, st: str, col: float) -> str:
  canonical = f"/cost/{slugify(city)}-{slugify(st)}/"
  h1 = clamp_title(f"{CONFIG.cost_title} in {city}, {st}", 70)

  inner = location_cost_section(city, st, col) + CONFIG.cost_body

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  description = clean_meta_description(content=CONFIG.cost_city_description, city=city, st=st)

  return make_page(
    mode=mode,
    h1=h1,
    canonical=canonical,
    nav_key="cost",
    inner=inner,
    description=description,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def howto_page_html(*, mode: Mode) -> str:
  inner = CONFIG.howto_body
  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")
  description = clean_meta_description(content=CONFIG.howto_description)

  return make_page(
    mode=mode,
    h1=CONFIG.howto_title,
    canonical=f"/{howto_slug()}/",
    nav_key="howto",
    inner=inner,
    description=description,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def state_homepage_html(*, mode: Mode) -> str:
  by_state = cities_by_state(CITIES)
  states = sorted(by_state.keys())

  links = "\n".join(
    f'<li><a href="{esc(href_state(mode, st))}">{esc(state_full(st))}</a></li>'
    for st in states
  )

  inner = (
    about_section()
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section()
    + """
<hr />
<h2>Our Service Area</h2>
<p class="muted">We provide services nationwide, including in the following states:</p>
<ul class="city-grid">
"""
    + links
    + """
</ul>
"""
  )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  description = clean_meta_description(content=CONFIG.home_description)

  return make_page(
    mode=mode,
    h1=CONFIG.h1_title,
    canonical="/",
    nav_key="home",
    inner=inner,
    description=description,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


def state_page_html(*, mode: Mode, st: str, cities: list[CityWithCol]) -> str:
  links = "\n".join(
    f'<li><a href="{esc(href_city(mode, c, st))}">{esc(c)}, {esc(st)}</a></li>'
    for c, st, _ in cities
  )

  inner = (
    about_section(st=state_full(st))
    + make_section(headings=CONFIG.main_h2, paras=CONFIG.main_p)
    + location_cost_section(st=state_full(st), col=STATE_TO_COL_MAP[st])
    + f"""
<h2>Cities we serve in {esc(state_full(st))}</h2>
<p class="muted">Choose your city to see local details and typical pricing ranges.</p>
<ul class="city-grid">
{links}
</ul>
""".strip()
  )

  show_cost = feature(mode, "cost")
  show_howto = feature(mode, "howto")

  description = clean_meta_description(content=CONFIG.state_description, st=st)

  return make_page(
    mode=mode,
    h1=clamp_title(f"{CONFIG.h1_short} in {state_full(st)}", 70),
    canonical=f"/{slugify(st)}/",
    nav_key="home",
    inner=inner,
    description=description,
    nav_show_cost=show_cost,
    nav_show_howto=show_howto,
    footer_show_cost=show_cost,
    footer_show_howto=show_howto,
  )


# ============================================================
# ROBOTS + SITEMAP + WRANGLER
# ============================================================

def robots_txt(*, mode: Mode) -> str:
  sm = canonical_for(mode, "/sitemap.xml")
  return f"User-agent: *\nAllow: /\nSitemap: {sm}\n"

def sitemap_xml(urls: list[str]) -> str:
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls)
    + "</urlset>\n"
  )

def wrangler_content() -> str:
  name = CONFIG.base_name.lower().replace(" ", "-")
  today = date.today().isoformat()
  return f"""{{
  "name": "{name}",
  "compatibility_date": "{today}",
  "assets": {{
    "directory": "./public"
  }}
}}
"""

def domain_from_site_origin() -> str:
  """
  Returns bare host like 'barndoorrepairspecialists.com' from SITE_ORIGIN.
  Falls back to SUBDOMAIN_BASE if set.
  """
  if SUBDOMAIN_BASE:
    return SUBDOMAIN_BASE.strip().lower().strip(".")
  if not SITE_ORIGIN:
    return ""
  host = SITE_ORIGIN.replace("https://", "").replace("http://", "").split("/")[0]
  return host.lower().strip().strip(".")

def vercel_json_for_subdomains(domain: str) -> str:
  """
  Generates vercel.json using Vercel 'routes' with host-based routing:
    - {city}.{domain}  ->  /{city}/...
    - excludes 'www' so www.{domain} is not treated as a city
  """
  if not domain:
    raise ValueError("Need domain to generate vercel.json (set SITE_ORIGIN or SUBDOMAIN_BASE)")

  d = re.escape(domain)

  obj = {
    "routes": [
      {
        "src": "/(.*)",
        "has": [
          {
            "type": "host",
            "value": rf"(?<city>(?!www$)[a-z0-9-]+)\.{d}"
          }
        ],
        "dest": "/$city/$1"
      }
    ]
  }
  return json.dumps(obj, indent=2) + "\n"




# ============================================================
# BUILD MODES
# ============================================================

def build_common(*, out: Path, mode: Mode) -> list[str]:
  """
  Writes shared core pages for the given mode.
  Returns list of sitemap URLs (relative or absolute depending on mode/canonicals).
  """
  urls: list[str] = ["/"]

  if feature(mode, "cost"):
    write_text(out / cost_slug() / "index.html", cost_page_html(mode=mode, include_city_index=(mode == "cost")))
    urls.append(f"/{cost_slug()}/")

  if feature(mode, "howto"):
    write_text(out / howto_slug() / "index.html", howto_page_html(mode=mode))
    urls.append(f"/{howto_slug()}/")

  if feature(mode, "contact"):
    write_text(out / "contact" / "index.html", contact_page_html(mode=mode))
    urls.append("/contact/")

  return urls


def build_regular(*, out: Path) -> None:
  mode: Mode = "regular"
  urls = build_common(out=out, mode=mode)
  write_text(out / "index.html", homepage_html(mode=mode))

  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(out / slug / "index.html", city_page_html(mode=mode, city=city, st=st, col=col, canonical=f"/{slug}/"))
    urls.append(f"/{slug}/")

  write_text(out / "robots.txt", robots_txt(mode=mode))
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ regular: Generated {len(urls)} pages into: {out.resolve()}")


def build_cost(*, out: Path) -> None:
  mode: Mode = "cost"
  urls = build_common(out=out, mode=mode)
  write_text(out / "index.html", homepage_html(mode=mode))

  # city pages
  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(out / slug / "index.html", city_page_html(mode=mode, city=city, st=st, col=col, canonical=f"/{slug}/"))
    urls.append(f"/{slug}/")

  # city cost pages
  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(out / "cost" / slug / "index.html", cost_city_page_html(mode=mode, city=city, st=st, col=col))
    urls.append(f"/cost/{slug}/")

  write_text(out / "robots.txt", robots_txt(mode=mode))
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ cost: Generated {len(urls)} pages into: {out.resolve()}")


def build_state(*, out: Path) -> None:
  mode: Mode = "state"
  urls = build_common(out=out, mode=mode)
  write_text(out / "index.html", state_homepage_html(mode=mode))

  by_state = cities_by_state(CITIES)
  for st, city_list in by_state.items():
    # /{st}/
    write_text(out / slugify(st) / "index.html", state_page_html(mode=mode, st=st, cities=city_list))
    urls.append(f"/{slugify(st)}/")

    # /{st}/{city}/
    for city, _, col in city_list:
      write_text(
        out / slugify(st) / slugify(city) / "index.html",
        city_page_html(mode=mode, city=city, st=st, col=col, canonical=f"/{slugify(st)}/{slugify(city)}/")
      )
      urls.append(f"/{slugify(st)}/{slugify(city)}/")

  write_text(out / "robots.txt", robots_txt(mode=mode))
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ state: Generated {len(urls)} pages into: {out.resolve()}")


def build_subdomain(*, out: Path) -> None:
  mode: Mode = "subdomain"

  here = Path(__file__).resolve().parent
  domain = domain_from_site_origin()
  write_text(here / "vercel.json", vercel_json_for_subdomains(domain))

  urls = build_common(out=out, mode=mode)  # this will write /contact/ on root domain

  # root homepage: NO city links
  write_text(out / "index.html", homepage_html(mode=mode))

  # root contact page (still fine)
  # build_common already wrote: /public/contact/index.html

  for city, st, col in CITIES:
    slug = city_subdomain_slug(city=city, st=st)
    canonical = abs_city_origin_subdomain(slug)  # ends with "/"

    # City "home" page (served at https://slug.domain/ via rewrite)
    write_text(
      out / slug / "index.html",
      city_page_html(mode=mode, city=city, st=st, col=col, canonical=canonical)
    )
    urls.append(canonical)

    contact_canon = canonical + "contact/"
    # City contact page (served at https://slug.domain/contact/ via rewrite)
    write_text(
      out / slug / "contact" / "index.html",
      contact_page_html(mode=mode, canonical=contact_canon)
    )
    urls.append(contact_canon)

  write_text(out / "robots.txt", robots_txt(mode=mode))
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ subdomain: Generated {len(urls)} pages into: {out.resolve()}")



def build_regular_city_only(*, out: Path) -> None:
  """
  regular_city_only:
    - Generates / (homepage) + city pages /{city-st}/ + /contact/
    - Does NOT generate /cost/ or /how-to/
    - Navbar/Footer hide Cost + How-To
    - City pages look exactly like regular mode city pages
  """
  mode: Mode = "regular_city_only"

  # build_common writes contact (because feature(mode, "contact") is True)
  # and returns sitemap URLs starting with "/"
  urls = build_common(out=out, mode=mode)

  # homepage (same factory as regular; it will hide Cost/How-To automatically)
  write_text(out / "index.html", homepage_html(mode=mode))

  # city pages (use the same factory as regular)
  for city, st, col in CITIES:
    slug = f"{slugify(city)}-{slugify(st)}"
    write_text(
      out / slug / "index.html",
      city_page_html(
        mode=mode,
        city=city,
        st=st,
        col=col,
        canonical=f"/{slug}/",
      ),
    )
    urls.append(f"/{slug}/")

  write_text(out / "robots.txt", robots_txt(mode=mode))
  write_text(out / "sitemap.xml", sitemap_xml([canonical_for(mode, u) for u in urls]))
  write_text(Path(__file__).resolve().parent / "wrangler.jsonc", wrangler_content())
  print(f"✅ regular_city_only: Generated {len(urls)} pages into: {out.resolve()}")



# ============================================================
# ENTRYPOINT
# ============================================================

VALID_MODES: set[str] = {"regular", "cost", "state", "subdomain", "regular_city_only"}

SITE_MODE: Mode = sys.argv[1] if len(sys.argv) > 1 else "regular"
COPY_IDX: int = resolve_copy_idx(SITE_MODE)  # reserved; not used

if SITE_MODE not in VALID_MODES:
  raise ValueError(
    f"Invalid SITE_MODE {SITE_MODE!r}. "
    f"Choose one of: {', '.join(sorted(VALID_MODES))}"
  )

def main() -> None:
  here = Path(__file__).resolve().parent
  out = here / CONFIG.output_dir

  reset_output_dir(out)
  copy_site_image(src_dir=here, out_dir=out, filename=CONFIG.image_filename)

  copy_static_files(
    src_dir=here,
    out_dir=out,
    filenames=FAVICON_FILES,
  )

  if SITE_MODE == "regular":  
    build_regular(out=out)
  elif SITE_MODE == "cost":
    build_cost(out=out)
  elif SITE_MODE == "state":
    build_state(out=out)
  elif SITE_MODE == "subdomain":
    build_subdomain(out=out)
  elif SITE_MODE == "regular_city_only":
    build_regular_city_only(out=out)
  else:
    raise ValueError(f"Unknown SITE_MODE: {SITE_MODE!r}")

if __name__ == "__main__":
  main()




