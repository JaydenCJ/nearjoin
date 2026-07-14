# nearjoin examples

Two small customer lists that pretend to come from different systems — a CRM
export and a billing export — with the messiness real exports have: legal
suffixes, abbreviations, accents, apostrophes, a typo'd trading name, a
house-number drift, and rows that exist on only one side.

| File | What it is |
| --- | --- |
| `customers_crm.csv` | 12 rows: `id,name,address,city` |
| `customers_billing.csv` | 11 rows: `account_id,customer,street_address,town` |

## 1. Join on company names

```bash
nearjoin join examples/customers_crm.csv examples/customers_billing.csv \
  --left-on name --right-on customer
```

Nine pairs match outright ("Smith & Sons Ltd" == "Smith and Sons Limited"),
"Northwind Traders" vs "Northwind Trading" lands in the review band, and
"Ironclad Security" / "Kings Cross Hardware" stay unmatched — correctly.

## 2. Join on addresses instead

```bash
nearjoin join examples/customers_crm.csv examples/customers_billing.csv \
  --left-on address --right-on street_address
```

The kind is auto-detected as `address`. "123 Main Street, Suite 4" matches
"123 Main St Ste 4" at 100; "45 Elm Avenue" vs "47 Elm Ave" is *rejected*
because the house numbers disagree, even though the strings look 90% alike.

## 3. Keep the leftovers

```bash
nearjoin join examples/customers_crm.csv examples/customers_billing.csv \
  --left-on name --right-on customer \
  -o matched.csv --unmatched-left crm_only.csv --unmatched-right billing_only.csv
```

## 4. Interrogate a single pair

```bash
nearjoin score "Northwind Traders" "Northwind Trading"
nearjoin keys "The Hilltop Bakery Inc."
```

`score` prints the full component/penalty breakdown; `keys` shows how a value
normalizes and which blocking keys it receives.
