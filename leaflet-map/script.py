import base64
import json
from pathlib import Path
import random
import streamlit as st
from streamlit_folium import st_folium
import folium
import sqlite3
import pandas as pd
from html import escape
from folium.plugins import MarkerCluster

st.set_page_config(layout="wide", page_title="Sydney Health Map & Analytics")

# 1. STYLING & STATUS SUPPRESSION
st.markdown("""
    <style>
        .block-container {
            padding: 0rem !important;
            max-width: 100% !important;
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Hide Streamlit status widget */
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

APP_DIR = Path(__file__).parent.resolve() 

# SQLite database is stored in the project root /data folder
DB_PATH = APP_DIR.parent / "data" / "health.db"


@st.cache_data
def load_hospitals(db_path, db_modified):
    """Retrieve transformed hospital records from SQLite."""

    with sqlite3.connect(db_path) as conn:
        hospitals = pd.read_sql_query(
            """
            SELECT hospital_id, hospital_name, state,
                   latitude, longitude, private, closed
            FROM hospitals
            """,
            conn
        )

    return hospitals


# Updated filename to match your team's repository
geojson_path = APP_DIR / "Greater Sydney - LGAs.json"
static_dir = APP_DIR / "static"

# Color map matching your JavaScript script
LGA_COLOR_MAP = {
    'Blacktown': '#FF6B6B',
    'Parramatta': '#4ECDC4',
    'Sydney': '#45B7D1',
    'Liverpool': '#96CEB4',
    'Canterbury-Bankstown': '#FFEAA7',
    'Cumberland': '#DDA0DD',
    'Fairfield': '#98D8C8',
}
DEFAULT_LGA_COLOR = '#B0B0B0'  # Grey fallback for other LGAs

def get_lga_color(lga_name):
    return LGA_COLOR_MAP.get(lga_name, DEFAULT_LGA_COLOR)

# 2. BASE64 MEDIA HELPER
def get_base64_image(image_path):
    if not image_path.exists():
        return None
    with open(image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode("utf-8")
    suffix = image_path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{mime_type};base64,{encoded}"

# 3. CACHED DATA PIPELINE WITH POPUP HTML & DYNAMIC PROPERTY DETECTION
@st.cache_data
def load_and_enrich_geojson(file_path):
    if not file_path.exists():
        st.error(f"GeoJSON file not found at: {file_path}")
        return None, []

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    geo_data = raw_data.get("LocalGovernmentArea", raw_data)
    lga_summary_list = []

    if "features" in geo_data:
        for feature in geo_data["features"]:
            props = feature.get("properties", {})
            
            # Extracts LGA name checking all fallback property keys from your JS code
            lga_name = (
                props.get("name") or 
                props.get("LGA_NAME") or 
                props.get("lga_name") or 
                props.get("LGA") or 
                props.get("lganame") or 
                "Unknown"
            )
            
            # Normalize property name back onto feature
            props["lga_name_resolved"] = lga_name
            props["lga_color"] = get_lga_color(lga_name)
            
            random.seed(lga_name)
            health_score_num = random.randint(72, 98)
            stats = {
                "lga_name": lga_name,
                "population_density": f"{random.randint(1200, 8500):,} / km²",
                "active_gps": random.randint(15, 120),
                "walkability_score": f"{random.randint(60, 98)}/100",
                "emergency_response": f"{random.randint(6, 14)} mins",
                "health_index_num": health_score_num,
                "health_index": f"{health_score_num}%",
            }
            
            # HTML Accordion Popup Card for direct map clicks
            popup_html = f"""
            <div style="font-family: sans-serif; width: 230px;">
                <h4 style="margin: 0 0 2px 0; font-size: 15px; color: #1a237e;">{lga_name}</h4>
                <span style="color: #666; font-size: 11px;">Local Government Health Profile</span>
                <hr style="margin: 6px 0 8px 0; border: 0; border-top: 1px solid #ddd;">
                
                <details open style="margin-bottom: 4px; border: 1px solid #e0e0e0; border-radius: 4px; padding: 4px 6px; background-color: #ffffff;">
                    <summary style="font-weight: bold; cursor: pointer; font-size: 12px; color: #333;">Healthcare Access</summary>
                    <div style="margin-top: 4px; font-size: 11px; color: #444; line-height: 1.5;">
                        <b>Active GP Clinics:</b> {stats['active_gps']}<br>
                        <b>Avg Emergency Response:</b> {stats['emergency_response']}
                    </div>
                </details>
                
                <details style="margin-bottom: 4px; border: 1px solid #e0e0e0; border-radius: 4px; padding: 4px 6px; background-color: #fafafa;">
                    <summary style="font-weight: bold; cursor: pointer; font-size: 12px; color: #333;">Liveability & Walkability</summary>
                    <div style="margin-top: 4px; font-size: 11px; color: #444; line-height: 1.5;">
                        <b>Walkability Score:</b> {stats['walkability_score']}<br>
                        <b>Population Density:</b> {stats['population_density']}
                    </div>
                </details>

                <details style="border: 1px solid #e0e0e0; border-radius: 4px; padding: 4px 6px; background-color: #fafafa;">
                    <summary style="font-weight: bold; cursor: pointer; font-size: 12px; color: #333;">Overall Index</summary>
                    <div style="margin-top: 4px; font-size: 11px; color: #08519c; font-weight: bold;">
                        Public Health Score: {stats['health_index']}
                    </div>
                </details>
            </div>
            """
            
            props.update(stats)
            props["popup_html"] = popup_html
            lga_summary_list.append(stats)

    lga_summary_list.sort(key=lambda x: x["health_index_num"], reverse=True)
    return geo_data, lga_summary_list

geo_data, lga_summary = load_and_enrich_geojson(geojson_path)

# Load hospitals from SQLite
if DB_PATH.exists():
    hospitals_df = load_hospitals(
        str(DB_PATH),
        DB_PATH.stat().st_mtime_ns
    )
else:
    hospitals_df = pd.DataFrame()
    st.warning("Hospital database not found. Run python pipeline.py first.")


# 4. SIDEBAR CONTROLS & INSPECTOR
st.sidebar.title("Map Controls & Rankings")
show_lgas = st.sidebar.toggle("Show LGA Boundaries", value=True)
show_markers = st.sidebar.toggle("Show Facility Markers", value=True)

show_markers = st.sidebar.toggle("Show Hospital Locations", value=True)

st.sidebar.caption(f"NSW hospital records: {len(hospitals_df)}")

st.sidebar.divider()

@st.fragment
def render_sidebar_inspector(lga_summary):
    st.subheader("LGA Health Index Ranking")

    if not lga_summary:
        st.warning("No LGA data available.")
        return

    options = ["None"] + [f"{item['lga_name']} ({item['health_index']})" for item in lga_summary]
    selected_option = st.selectbox("Select LGA to Inspect:", options)
    
    if selected_option != "None":
        selected_lga_name = selected_option.split(" (")[0]
        selected_lga_data = next((item for item in lga_summary if item["lga_name"] == selected_lga_name), None)
        
        if selected_lga_data:
            st.markdown(f"### 📊 Profile: {selected_lga_data['lga_name']}")
            
            with st.expander("Healthcare Access", expanded=True):
                st.write(f"**Active GP Clinics:** {selected_lga_data['active_gps']}")
                st.write(f"**Avg Emergency Response:** {selected_lga_data['emergency_response']}")

            with st.expander("Liveability & Walkability", expanded=False):
                st.write(f"**Walkability Score:** {selected_lga_data['walkability_score']}")
                st.write(f"**Population Density:** {selected_lga_data['population_density']}")

            with st.expander("Overall Index", expanded=True):
                st.write(f"**Public Health Score:** :blue[{selected_lga_data['health_index']}]")

with st.sidebar:
    render_sidebar_inspector(lga_summary)
    st.caption("Data source: NSW Spatial Services & Mocked Health Analytics")

# 5. FOLIUM MAP CREATION
m = folium.Map(location=[-33.8688, 151.2093], zoom_start=11, tiles="OpenStreetMap")

if show_lgas and geo_data:
    folium.GeoJson(
        geo_data,
        name="Greater Sydney LGAs",
        smooth_factor=1.5,
        zoom_on_click=False,
        style_function=lambda feature: {
            "fillColor": "#3182bd",   # Light blue fill
            "color": "#08519c",       # Medium blue outline border
            "weight": 1.2,
            "fillOpacity": 0.25,      # Light, transparent overlay
            "opacity": 0.8
        },
        highlight_function=lambda x: {
            "fillColor": "#002b53",   # Dark navy on hover
            "color": "#00152a",
            "weight": 2.0,
            "fillOpacity": 0.50,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["lga_name_resolved", "health_index"],
            aliases=["LGA:", "Health Score:"],
            style="background-color: white; color: #333; font-family: sans-serif; font-size: 12px; padding: 4px 8px; border-radius: 3px;"
        ),
        popup=folium.GeoJsonPopup(
            fields=["popup_html"],
            labels=False
        )
    ).add_to(m)

# 7.  HOSPITAL MARKERS
if show_markers and not hospitals_df.empty:

    # Create a marker cluster
    hospital_cluster = MarkerCluster(
        name="NSW Hospitals"
    ).add_to(m)

    # Loop through hospital records
    for _, hospital in hospitals_df.iterrows():

        hospital_name = escape(str(hospital["hospital_name"]))
        hospital_id = escape(str(hospital["hospital_id"]))

        # Determine hospital classification
        hospital_type = (
            "Private Hospital"
            if hospital["private"]
            else "Public Hospital"
        )

        hospital_status = (
            "Closed"
            if hospital["closed"]
            else "Not marked as closed"
        )

        # Create popup HTML
        popup_html = f"""
        <div style="font-family: Arial; width: 220px;">
            <h4 style="color: #1a237e; margin-bottom: 6px;">
                {hospital_name}
            </h4>

            <b>Hospital ID:</b> {hospital_id}<br>
            <b>Type:</b> {hospital_type}<br>
            <b>Status:</b> {hospital_status}<br>
            <b>State:</b> NSW<br>

            <hr>

            <b>Latitude:</b> {hospital['latitude']:.6f}<br>
            <b>Longitude:</b> {hospital['longitude']:.6f}
        </div>
        """

        # Different marker colours for private/public
        marker_color = (
            "purple" if hospital["private"] else "blue"
        )

        folium.Marker(
            location=[
                hospital["latitude"],
                hospital["longitude"]
            ],
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=hospital_name,
            icon=folium.Icon(
                color=marker_color,
                icon="plus-sign"
            )
        ).add_to(hospital_cluster)


# 8. RENDER MAP
st_folium(
    m,
    use_container_width=True,
    height=850,
    returned_objects=[],
    key="sydney_health_map"
)