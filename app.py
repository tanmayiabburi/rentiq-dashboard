import hashlib, json, os, re, secrets
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="RentIQ - Hyderabad Rental Analytics", page_icon="🏠", layout="wide")

USERS, DATA = "users.json", "final_data.csv"
def _secret(name, default):
    try:
        return st.secrets[name]
    except Exception:
        return os.environ.get(name, default)

ADMIN_NAME = "Administrator"
ADMIN_EMAIL = "admin@rentiq.com"
ADMIN_PASSWORD = _secret("ADMIN_PASSWORD", "Admin@RentIQ2026")  # set the real one in Streamlit Secrets
ORDER = ["RK1", "BHK1", "BHK2", "BHK3", "BHK4", "BHK4PLUS"]
AMEN = {"Gym": "GYM", "Lift": "LIFT", "Swimming pool": "POOL", "Internet": "INTERNET", "Air conditioning": "AC",
        "Club house": "CLUB", "Intercom": "INTERCOM", "Security": "SECURITY", "Park": "PARK", "Servant room": "SERVANT"}
BLUE, NAVY, ORANGE = "#2563eb", "#1e3a8a", "#f97316"


# ---------- accounts (stored in users.json, passwords hashed with PBKDF2) ----------
def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()

def load_users():
    if os.path.exists(USERS):
        with open(USERS) as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS, "w") as f:
        json.dump(users, f, indent=2)

def add_user(name, email, pw, role="user"):
    users = load_users()
    salt = secrets.token_hex(16)
    users.append({"name": name, "email": email.lower(), "role": role, "salt": salt,
                  "hash": _hash(pw, salt), "created": datetime.now().strftime("%Y-%m-%d")})
    save_users(users)

def check_login(email, pw):
    for u in load_users():
        if u["email"] == email.lower().strip() and _hash(pw, u["salt"]) == u["hash"]:
            return u
    return None

if not any(u["role"] == "admin" for u in load_users()):
    add_user(ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")


# ---------- login / register page ----------
def auth_page():
    st.markdown("""
    <style>
    .hero{background:linear-gradient(135deg,#1e3a8a,#2563eb 55%,#f97316);color:#fff;padding:48px;border-radius:20px;min-height:430px}
    .hero h1{font-size:38px;line-height:1.15;margin:30px 0 14px;color:#fff}
    .hero p{opacity:.92;line-height:1.6}
    .pill{display:inline-block;background:rgba(255,255,255,.2);padding:6px 12px;border-radius:99px;font-size:13px;margin:4px 6px 0 0}
    </style>""", unsafe_allow_html=True)
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown("""<div class="hero"><b style="font-size:22px">🏠 RentIQ</b>
        <h1>Understand Hyderabad's rental market.</h1>
        <p>Explore rent, deposits, property sizes and amenities across 18,000+ listings and 2,400+ localities.</p>
        <span class="pill">Rent vs deposit</span><span class="pill">BHK analysis</span><span class="pill">Amenity impact</span></div>""",
                    unsafe_allow_html=True)
    with right:
        tab_in, tab_up = st.tabs(["Sign in", "Create account"])
        with tab_in:
            with st.form("login"):
                st.subheader("Welcome back")
                email = st.text_input("Email")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Sign in", use_container_width=True):
                    u = check_login(email, pw)
                    if u:
                        st.session_state.user = u
                        st.rerun()
                    st.error("Incorrect email or password.")
        with tab_up:
            with st.form("register"):
                st.subheader("Create your account")
                name = st.text_input("Full name")
                email = st.text_input("Email ")
                pw = st.text_input("Password (min 8 characters)", type="password")
                pw2 = st.text_input("Confirm password", type="password")
                if st.form_submit_button("Create account", use_container_width=True):
                    if len(name.strip()) < 2:
                        st.error("Please enter your full name.")
                    elif not re.match(r"^\S+@\S+\.\S+$", email):
                        st.error("Enter a valid email address.")
                    elif len(pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif pw != pw2:
                        st.error("Passwords do not match.")
                    elif any(u["email"] == email.lower() for u in load_users()):
                        st.error("An account with this email already exists.")
                    else:
                        add_user(name.strip(), email, pw)
                        st.success("Account created. Go to the Sign in tab.")


# ---------- dashboard ----------
HOUSE = [BLUE, NAVY, ORANGE, "#10b981", "#a855f7", "#ec4899"]

@st.cache_data
def get_data():
    d = pd.read_csv(DATA)
    if "location" in d.columns:
        ll = d["location"].astype(str).str.split(",", expand=True)
        if ll.shape[1] >= 2:
            d["lat"] = pd.to_numeric(ll[0], errors="coerce")
            d["lon"] = pd.to_numeric(ll[1], errors="coerce")
    return d

def fmt(n):
    for lim, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= lim:
            return f"{n / lim:.1f}{s}"
    return f"{n:,.0f}"

def show(fig, key, select=False):
    """Draw a plotly chart; with select=True the user can click or drag to select points."""
    fig.update_layout(template="plotly_white", margin=dict(t=50, b=20, l=10, r=10))
    if select:
        try:
            return st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=key)
        except TypeError:
            pass
    st.plotly_chart(fig, use_container_width=True, key=key)
    return None

def filters(df):
    sb = st.sidebar
    bhks = [b for b in ORDER if b in set(df.type_bhk)]
    furs = sorted(df.furnishingDesc.dropna().unique())
    if sb.button("Reset all filters", use_container_width=True):
        for k in [k for k in st.session_state if k.startswith("f_")]:
            del st.session_state[k]
        st.rerun()
    sel_bhk = sb.multiselect("BHK type", bhks, default=bhks, key="f_bhk")
    sel_fur = sb.multiselect("Furnishing", furs, default=furs, key="f_fur")
    lo, hi = int(df.rent_amount.min()), int(df.rent_amount.max())
    rent = sb.slider("Monthly rent (₹)", lo, hi, (lo, hi), step=1000, key="f_rent")
    maint = sb.radio("Maintenance", ["Any", "Maintenance extra", "No maintenance"], key="f_maint")
    need = sb.multiselect("Must have amenities", list(AMEN), key="f_need")
    locs = sb.multiselect("Localities (type to search)", sorted(df.locality.dropna().unique()), key="f_loc")
    d = df[df.type_bhk.isin(sel_bhk) & df.furnishingDesc.isin(sel_fur) & df.rent_amount.between(rent[0], rent[1])]
    if maint != "Any":
        d = d[d.isMaintenance == (maint == "Maintenance extra")]
    for a in need:
        d = d[d[AMEN[a]]]
    if locs:
        d = d[d.locality.isin(locs)]
    return d, sel_bhk

def amenity_table(d):
    rows = []
    for name, col in AMEN.items():
        w, wo = d[d[col]], d[~d[col]]
        up = (w.rent_amount.mean() / wo.rent_amount.mean() - 1) * 100 if len(w) and len(wo) else 0
        rows.append([name, d[col].mean() * 100, up])
    return pd.DataFrame(rows, columns=["Amenity", "Availability %", "Rent uplift %"])

def dashboard(user):
    df = get_data()
    st.sidebar.markdown(f"### 🏠 RentIQ\n**{user['name']}**" + (" · Admin" if user["role"] == "admin" else ""))
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()
    st.sidebar.divider()
    st.sidebar.subheader("Filters")
    d, sel_bhk = filters(df)

    st.title("Hyderabad Rental Dashboard")
    st.caption(f"Showing **{len(d):,}** of {len(df):,} listings · change the filters on the left and every chart updates.")
    if d.empty:
        st.warning("No listings match these filters. Try widening them or press Reset all filters.")
        return

    if user["role"] == "admin":
        with st.expander("Manage users"):
            users = [{k: v for k, v in u.items() if k not in ("salt", "hash")} for u in load_users()]
            st.dataframe(pd.DataFrame(users), use_container_width=True)
            others = [u["email"] for u in users if u["role"] != "admin"]
            if others:
                target = st.selectbox("Delete user", others)
                if st.button("Delete"):
                    save_users([u for u in load_users() if u["email"] != target])
                    st.rerun()

    cols = st.columns(5)
    for c, (label, val, tot) in zip(cols, [("Sum of deposit", d.deposit.sum(), df.deposit.sum()),
                                           ("Sum of rent amount", d.rent_amount.sum(), df.rent_amount.sum()),
                                           ("Sum of floor", d.floor.sum(), df.floor.sum()),
                                           ("Sum of bathroom", d.bathroom.sum(), df.bathroom.sum()),
                                           ("Sum of property size", d.property_size.sum(), df.property_size.sum())]):
        c.metric(label, fmt(val), f"{val / tot * 100:.0f}% of all", delta_color="off")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "📍 Localities", "🗺️ Map", "🛋️ Amenities & rent explorer", "🔎 Data explorer"])

    # ---- Overview ----
    with tab1:
        top = d.locality.value_counts().head(40).index
        loc = d[d.locality.isin(top)].groupby(["locality", "isMaintenance"])[["deposit", "rent_amount"]].sum().reset_index()
        loc["Maintenance"] = loc.isMaintenance.map({True: "Maintenance extra", False: "No maintenance"})
        a, b = st.columns([2, 1])
        with a:
            fig1 = px.scatter(loc, x="deposit", y="rent_amount", color="Maintenance", custom_data=["locality"],
                              hover_name="locality", color_discrete_map={"No maintenance": BLUE, "Maintenance extra": ORANGE},
                              title="Deposit vs rent by locality (click or drag to select points)")
            ev = show(fig1, "scatter", select=True)
        with b:
            fur = d.groupby("furnishingDesc").rent_amount.sum().reset_index()
            show(px.pie(fur, names="furnishingDesc", values="rent_amount", hole=0.55,
                        color_discrete_sequence=HOUSE, title="Share of rent by furnishing"), "pie")
        picked = []
        try:
            picked = sorted({p["customdata"][0] for p in ev.selection.points})
        except Exception:
            pass
        if picked:
            st.success("Selected localities: " + ", ".join(picked))
            sel = d[d.locality.isin(picked)].groupby("type_bhk").agg(
                listings=("rent_amount", "size"), avg_rent=("rent_amount", "mean"), avg_deposit=("deposit", "mean")).round(0)
            st.dataframe(sel, use_container_width=True)
        g = d.groupby("type_bhk")[["deposit", "property_size", "rent_amount"]].sum().reindex(ORDER).dropna()
        sizes = [14 if b in sel_bhk else 7 for b in g.index]
        fig5 = go.Figure()
        for col, name, color in [("deposit", "Sum of deposit", BLUE), ("property_size", "Sum of property size", NAVY),
                                 ("rent_amount", "Sum of rent amount", ORANGE)]:
            fig5.add_trace(go.Scatter(x=g.index, y=g[col], name=name, mode="lines+markers", line_shape="spline",
                                      marker=dict(size=sizes, color=color), line=dict(color=color)))
        fig5.update_yaxes(type="log")
        fig5.update_layout(title="Deposit, rent and property size by BHK type (log scale)")
        show(fig5, "line")
        am = amenity_table(d)
        best = am.sort_values("Rent uplift %").iloc[-1]
        byb = d.groupby("type_bhk").rent_amount.mean().sort_values()
        st.subheader("Key insights")
        st.markdown(f"- **{len(d):,}** listings selected, average rent **₹{d.rent_amount.mean():,.0f}**, "
                    f"average deposit **₹{d.deposit.mean():,.0f}**\n"
                    f"- Highest average rent: **{byb.index[-1]}** at ₹{byb.iloc[-1]:,.0f}\n"
                    f"- Biggest rent premium comes from **{best['Amenity']}** (+{best['Rent uplift %']:.0f}% on average)")

    # ---- Localities ----
    with tab2:
        c1, c2, c3 = st.columns(3)
        n = c1.slider("How many localities", 5, 30, 15)
        metric = c2.selectbox("Rank by", ["Total rent", "Average rent", "Average deposit", "Number of listings"])
        minn = c3.slider("Minimum listings per locality", 1, 50, 10)
        colname = {"Total rent": "total_rent", "Average rent": "avg_rent", "Average deposit": "avg_deposit", "Number of listings": "listings"}[metric]
        g = d.groupby("locality").agg(total_rent=("rent_amount", "sum"), avg_rent=("rent_amount", "mean"),
                                      avg_deposit=("deposit", "mean"), listings=("rent_amount", "size"))
        g = g[g.listings >= minn].sort_values(colname, ascending=False).head(n)
        if g.empty:
            st.info("No locality has that many listings. Lower the minimum.")
        else:
            show(px.bar(g.reset_index().sort_values(colname), x=colname, y="locality", orientation="h",
                        color_discrete_sequence=[BLUE], title=f"Top localities by {metric.lower()}"), "locbar")
            cmp = st.multiselect("Compare localities (average rent by BHK type)", sorted(d.locality.unique()), default=list(g.index[:3]))
            if cmp:
                cm = d[d.locality.isin(cmp)].groupby(["locality", "type_bhk"]).rent_amount.mean().reset_index()
                show(px.bar(cm, x="type_bhk", y="rent_amount", color="locality", barmode="group",
                            category_orders={"type_bhk": ORDER}, color_discrete_sequence=HOUSE,
                            title="Average rent by BHK type"), "cmp")

    # ---- Map ----
    with tab3:
        if "lat" in d.columns:
            m = d.dropna(subset=["lat", "lon"])
            m = m[m.lat.between(16, 19) & m.lon.between(77, 80)]
            if len(m):
                m = m.sample(min(3000, len(m)), random_state=1)
                fig = px.scatter_mapbox(m, lat="lat", lon="lon", color="rent_amount", hover_name="locality",
                                        hover_data={"type_bhk": True, "rent_amount": True, "lat": False, "lon": False},
                                        color_continuous_scale="Turbo", range_color=(0, m.rent_amount.quantile(0.95)),
                                        zoom=9.5, center=dict(lat=17.42, lon=78.45), height=620, title="Listings by rent (sample of up to 3,000)")
                fig.update_layout(mapbox_style="open-street-map", margin=dict(t=50, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True, key="map")
            else:
                st.info("No listings with coordinates for these filters.")
        else:
            st.info("The map needs the original dataset with its location column. Upload the full final_data.csv.")

    # ---- Amenities & rent explorer ----
    with tab4:
        am = amenity_table(d)
        a, b = st.columns(2)
        with a:
            show(px.bar(am.sort_values("Availability %"), x="Availability %", y="Amenity", orientation="h",
                        title="Amenity availability (% of listings)", color_discrete_sequence=[BLUE]), "av")
        with b:
            show(px.bar(am.sort_values("Rent uplift %"), x="Rent uplift %", y="Amenity", orientation="h",
                        title="What drives rent? (average rent uplift %)", color_discrete_sequence=[ORANGE]), "up")
        st.subheader("Rent explorer")
        st.caption("Pick a flat type and see what similar listings across Hyderabad actually rent for.")
        c1, c2, c3 = st.columns(3)
        eb = c1.selectbox("BHK type", [b for b in ORDER if b in set(df.type_bhk)], index=2)
        ef = c2.selectbox("Furnishing", sorted(df.furnishingDesc.dropna().unique()))
        ea = c3.multiselect("Amenities", list(AMEN))
        mm = df[(df.type_bhk == eb) & (df.furnishingDesc == ef)]
        for x in ea:
            mm = mm[mm[AMEN[x]]]
        if len(mm) >= 5:
            r1, r2, r3 = st.columns(3)
            r1.metric("Typical rent (median)", f"₹{mm.rent_amount.median():,.0f}")
            r2.metric("Usual range (25th–75th %)", f"₹{mm.rent_amount.quantile(.25):,.0f} – ₹{mm.rent_amount.quantile(.75):,.0f}")
            r3.metric("Matching listings", f"{len(mm):,}")
        else:
            st.warning("Fewer than 5 listings match this combination. Remove an amenity.")

    # ---- Data explorer ----
    with tab5:
        q = st.text_input("Search locality")
        t = d[d.locality.str.contains(q, case=False, na=False)] if q else d
        show_cols = ["locality", "type_bhk", "furnishingDesc", "property_size", "bathroom", "floor", "rent_amount", "deposit", "isMaintenance"]
        st.dataframe(t[show_cols], use_container_width=True, height=420)
        st.download_button("Download filtered data (CSV)", t.to_csv(index=False).encode(), "filtered_listings.csv", "text/csv")


if st.session_state.get("user"):
    dashboard(st.session_state.user)
else:
    auth_page()
