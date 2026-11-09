"""Generate Veridash's three synthetic example datasets (seeded, reproducible).

All company, store, product and ticker names are fictional.
Each dataset includes a few intentional data issues so the health check has
something real to find.

Run from the project root:  python -m data.samples.generate_samples
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT_DIR = Path(__file__).resolve().parent
SEED = 20240611


def make_retail(rng: np.random.Generator, n: int = 4_960) -> pd.DataFrame:
    """Retail sales transactions with seasonality, growth and a few data issues.

    Intentional issues: unit_price stored as "$" text with a few "TBD" values
    (mixed type), missing discounts and regions, duplicate rows and a handful
    of bulk orders that show up as outliers.
    """
    stores = {
        "Harbor Point": "East", "Maple Commons": "East", "Riverside Plaza": "South",
        "Cedar Crossing": "South", "Summit Square": "West", "Pacific Row": "West",
        "Lakeshore Mall": "Central", "Prairie Market": "Central", "North Gate": "North",
        "Pinecrest": "North",
    }
    catalog = {
        "Electronics": [("Aurora Headphones", 129.0), ("Lumen Smart Lamp", 59.0), ("Volt Power Bank", 39.0)],
        "Home": [("Nest & Oak Throw", 45.0), ("Brightline Cookware Set", 149.0), ("Calm Diffuser", 29.0)],
        "Apparel": [("Trailhead Jacket", 119.0), ("Everyday Tee", 19.0), ("Stride Sneakers", 89.0)],
        "Grocery": [("Morning Roast Coffee", 14.0), ("Harvest Granola", 7.5), ("Sparkling Citrus 12pk", 9.0)],
        "Sports": [("Peak Yoga Mat", 35.0), ("Ridge Water Bottle", 24.0), ("Pulse Fitness Band", 79.0)],
    }
    dates = pd.to_datetime("2023-01-01") + pd.to_timedelta(rng.integers(0, 731, n), unit="D")
    day_index = (dates - dates.min()).days.to_numpy()
    month = dates.month.to_numpy()
    seasonal = 1.0 + 0.35 * np.isin(month, [11, 12]) + 0.1 * np.isin(month, [6, 7])
    growth = 1.0 + 0.18 * day_index / 730

    store_names = rng.choice(list(stores), n, p=[0.13, 0.08, 0.12, 0.09, 0.12, 0.1, 0.11, 0.09, 0.08, 0.08])
    cat_names = rng.choice(list(catalog), n, p=[0.26, 0.2, 0.22, 0.17, 0.15])
    products, base_prices = [], []
    for cat in cat_names:
        name, price = catalog[cat][rng.integers(0, 3)]
        products.append(name)
        base_prices.append(price)
    base_prices = np.array(base_prices)
    unit_price = np.round(base_prices * rng.uniform(0.95, 1.05, n), 2)
    units = np.maximum(1, rng.poisson(2.2 * seasonal * growth)).astype(int)
    bulk = rng.choice(n, 14, replace=False)
    units[bulk] = units[bulk] * rng.integers(25, 45, len(bulk))
    discount = np.round(rng.choice([0, 0, 0, 0.05, 0.1, 0.15, 0.2, 0.25], n), 2)
    revenue = np.round(units * unit_price * (1 - discount), 2)
    cost = np.round(units * unit_price * rng.uniform(0.52, 0.68, n), 2)

    df = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "store": store_names,
            "region": [stores[s] for s in store_names],
            "category": cat_names,
            "product": products,
            "units": units,
            "unit_price": [f"${p:,.2f}" for p in unit_price],
            "discount": discount,
            "revenue": revenue,
            "cost": cost,
        }
    ).sort_values("date", kind="stable")

    df["discount"] = df["discount"].astype("float64")
    df.loc[df.sample(frac=0.03, random_state=1).index, "discount"] = np.nan
    df.loc[df.sample(frac=0.01, random_state=2).index, "region"] = np.nan
    df.loc[df.sample(n=7, random_state=3).index, "unit_price"] = "TBD"
    dupes = df.sample(n=40, random_state=4)
    return pd.concat([df, dupes]).sort_values("date", kind="stable").reset_index(drop=True)


def make_hr(rng: np.random.Generator, n: int = 1_488) -> pd.DataFrame:
    """HR workforce snapshot with attrition drivers and a few data issues.

    Intentional issues: missing satisfaction scores, a constant "company"
    column and duplicate employee rows.
    """
    departments = {
        "Engineering": ["Software Engineer", "Senior Engineer", "Engineering Manager"],
        "Sales": ["Account Executive", "Sales Manager", "Sales Associate"],
        "Operations": ["Operations Analyst", "Logistics Coordinator", "Operations Lead"],
        "Finance": ["Financial Analyst", "Accountant", "Controller"],
        "Marketing": ["Marketing Specialist", "Content Strategist", "Brand Manager"],
        "Support": ["Support Specialist", "Support Lead", "Customer Success Manager"],
        "People": ["HR Generalist", "Recruiter", "People Partner"],
    }
    dept = rng.choice(list(departments), n, p=[0.26, 0.18, 0.15, 0.1, 0.1, 0.14, 0.07])
    role_idx = rng.choice(3, n, p=[0.6, 0.28, 0.12])
    roles = [departments[d][i] for d, i in zip(dept, role_idx, strict=True)]
    hire = pd.to_datetime("2013-01-01") + pd.to_timedelta(rng.integers(0, 4_700, n), unit="D")
    snapshot = pd.Timestamp("2025-12-31")
    tenure = np.round((snapshot - hire).days / 365.25, 1)
    band_num = np.clip(1 + role_idx * 2 + (tenure > 5).astype(int) + rng.integers(0, 2, n), 1, 6)
    performance = np.clip(np.round(rng.normal(3.4, 0.8, n)), 1, 5).astype(int)
    overtime = rng.random(n) < np.where(np.isin(dept, ["Sales", "Support"]), 0.42, 0.22)
    satisfaction = np.clip(np.round(rng.normal(3.7, 0.7, n) - 0.6 * overtime + 0.1 * (performance - 3), 1), 1, 5)
    logit = -2.3 + 1.1 * overtime - 0.9 * (satisfaction - 3.5) - 0.12 * np.minimum(tenure, 10)
    attrition = rng.random(n) < 1 / (1 + np.exp(-logit))

    df = pd.DataFrame(
        {
            "employee_id": [f"E{10001 + i}" for i in range(n)],
            "company": "Northbeam Labs",
            "department": dept,
            "role": roles,
            "hire_date": hire.strftime("%Y-%m-%d"),
            "tenure": tenure,
            "salary_band": [f"B{b}" for b in band_num],
            "performance_rating": performance,
            "satisfaction": satisfaction,
            "overtime": np.where(overtime, "Yes", "No"),
            "attrition": np.where(attrition, "Yes", "No"),
        }
    )
    df.loc[df.sample(frac=0.06, random_state=5).index, "satisfaction"] = np.nan
    dupes = df.sample(n=12, random_state=6)
    return pd.concat([df, dupes]).reset_index(drop=True)


def make_portfolio(rng: np.random.Generator, n: int = 1_980) -> pd.DataFrame:
    """Investment holdings lots across fictional tickers with a few data issues.

    Intentional issues: missing prices (so market value and gain/loss are
    missing too), a constant "currency" column, duplicate lots and a few very
    large positions.
    """
    tickers = {
        "QVRA": ("Technology", 182.0, 0.22), "ZENT": ("Technology", 64.0, 0.30),
        "LYMX": ("Healthcare", 118.0, 0.08), "HALO": ("Healthcare", 41.0, 0.15),
        "BRKN": ("Financials", 73.0, 0.05), "TRSV": ("Financials", 29.0, -0.04),
        "VOLQ": ("Energy", 55.0, -0.10), "SOLR": ("Energy", 22.0, 0.25),
        "MRDN": ("Consumer", 96.0, 0.06), "CAVO": ("Consumer", 38.0, -0.02),
        "FRGX": ("Industrials", 140.0, 0.10), "PYLN": ("Utilities", 47.0, 0.02),
    }
    months = pd.date_range("2023-01-31", "2024-12-31", freq="ME")
    walk: dict[str, np.ndarray] = {}
    for t, (_, start, drift) in tickers.items():
        shocks = rng.normal(drift / 12, 0.06, len(months))
        walk[t] = start * np.exp(np.cumsum(shocks))

    tick = rng.choice(list(tickers), n)
    m_idx = rng.integers(0, len(months), n)
    buy_idx = np.maximum(0, m_idx - rng.integers(1, 18, n))
    price = np.array([walk[t][i] for t, i in zip(tick, m_idx, strict=True)])
    buy_price = np.array([walk[t][i] for t, i in zip(tick, buy_idx, strict=True)])
    shares = np.maximum(1, np.round(rng.lognormal(3.4, 0.7, n))).astype(int)
    whales = rng.choice(n, 10, replace=False)
    shares[whales] = shares[whales] * 40
    price = np.round(price, 2)
    market_value = np.round(shares * price, 2)
    cost_basis = np.round(shares * buy_price * rng.uniform(0.97, 1.03, n), 2)

    df = pd.DataFrame(
        {
            "date": months[m_idx].strftime("%Y-%m-%d"),
            "ticker": tick,
            "sector": [tickers[t][0] for t in tick],
            "shares": shares,
            "price": price,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "gain_loss": np.round(market_value - cost_basis, 2),
            "currency": "USD",
        }
    ).sort_values(["date", "ticker"], kind="stable")
    gap = df.sample(frac=0.015, random_state=7).index
    df.loc[gap, ["price", "market_value", "gain_loss"]] = np.nan
    dupes = df.sample(n=20, random_state=8)
    return pd.concat([df, dupes]).sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)


def main() -> None:
    """Write the three sample datasets into this folder."""
    rng = np.random.default_rng(SEED)
    make_retail(rng).to_csv(OUT_DIR / "retail_sales.csv", index=False)
    hr = make_hr(rng)
    with pd.ExcelWriter(OUT_DIR / "hr_workforce.xlsx", engine="openpyxl") as writer:
        hr.to_excel(writer, sheet_name="Employees", index=False)
        pd.DataFrame(
            {
                "field": ["source", "snapshot_date", "note"],
                "value": ["Synthetic data generated by Veridash", "2025-12-31", "Fictional company"],
            }
        ).to_excel(writer, sheet_name="About", index=False)
    make_portfolio(rng).to_csv(OUT_DIR / "investment_portfolio.csv", index=False)
    print(f"Wrote samples to {OUT_DIR}")


if __name__ == "__main__":
    main()
