import json
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
import logging 

# --- Configure Logging ---
logging.basicConfig(
    level=logging.INFO,
    filename="logs/ml.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)


# ---------------------------------
# Load raw scan results
# ---------------------------------
with open("defi_scan_results.json", "r") as f:
    data = json.load(f)

yields = pd.DataFrame(data.get("yields", []))
memes = pd.DataFrame(data.get("memes", []))

# ---------------------------------
# Helper function to convert strings to numeric
# ---------------------------------
def to_float(df, cols):
    """
    Convert columns with strings like "$1,234.56" or "12.34%" to float.
    """
    for col in cols:
        # Use raw string for regex to avoid unsupported escape sequence
        df[col] = df[col].replace(r'[\$, %]', '', regex=True).astype(float)
    return df

# ---------------------------------
# Enhance Yield Opportunities
# ---------------------------------
if not yields.empty:
    yields = to_float(yields, ["apy", "tvl", "ror", "gas_fee"])
    features_yields = ["apy", "tvl", "ror", "gas_fee"]
    X_yields = yields[features_yields]
    y_target_yields = yields["ror"]

    scaler_y = StandardScaler()
    X_y_scaled = scaler_y.fit_transform(X_yields)

    rf_yields = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_yields.fit(X_y_scaled, y_target_yields)

    yields["predicted_ror"] = rf_yields.predict(X_y_scaled)

    # Risk-adjusted score: higher predicted_ror and lower risk = better
    risk_map = {"Low": 1.0, "Medium": 0.7, "High": 0.4}  # adjustable weights
    yields["risk_score"] = yields["risk"].map(risk_map)
    yields["final_score"] = yields["predicted_ror"] * yields["risk_score"]

    # Sort descending
    yields = yields.sort_values("final_score", ascending=False)

# ---------------------------------
# Enhance Meme Coins
# ---------------------------------
if not memes.empty:
    memes = to_float(memes, ["liquidity_usd", "volume_24h_usd", "market_cap", "change_24h_pct"])
    features_memes = ["liquidity_usd", "volume_24h_usd", "market_cap", "change_24h_pct"]
    X_memes = memes[features_memes]
    y_target_memes = memes["change_24h_pct"]

    scaler_m = StandardScaler()
    X_m_scaled = scaler_m.fit_transform(X_memes)

    rf_memes = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_memes.fit(X_m_scaled, y_target_memes)

    memes["predicted_growth"] = rf_memes.predict(X_m_scaled)

    # Risk adjustment: high volatility reduces score
    memes["risk_score"] = 1 - (abs(memes["change_24h_pct"]) / 100)  # normalize 0-1
    memes["final_score"] = memes["predicted_growth"] * memes["risk_score"]
    memes = memes.sort_values("final_score", ascending=False)

# ---------------------------------
# Save enhanced results
# ---------------------------------
enhanced_scan = {
    "yields": yields.to_dict(orient="records"),
    "memes": memes.to_dict(orient="records")
}

with open("defi_scan_results_enhanced.json", "w") as f:
    json.dump(enhanced_scan, f, indent=2)

# ---------------------------------
# Print human-readable top 10 results
# ---------------------------------
def print_top(df, cols, title, n=10):
    print(f"\n=== Top {n} {title} ===")
    print(df[cols].head(n).to_string(index=False))

if not yields.empty:
    print_top(
        yields,
        ["project", "apy", "tvl", "ror", "risk", "predicted_ror", "final_score"],
        "Yield Opportunities",
        n=10
    )

if not memes.empty:
    print_top(
        memes,
        ["symbol", "price_usd", "liquidity_usd", "volume_24h_usd", "change_24h_pct", "predicted_growth", "final_score"],
        "Meme Coin Opportunities",
        n=10
    )

print("\nEnhanced scan saved to defi_scan_results_enhanced.json")
