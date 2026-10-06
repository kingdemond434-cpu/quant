# Awesome Alternative Data [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

A curated list of alternative data sources for investment research, market
intelligence, and quantitative analysis: web-scraped data, satellite imagery,
transaction data, sentiment, geolocation, and the infrastructure around them.

Free and open sources are marked. Access restrictions and realistic cost bands
are stated, because a list that mixes a free government feed with a $400k/year
satellite subscription without saying so is not useful to anyone.

---

## What this covers

Alternative data means anything outside traditional financial statements,
filings, and market prices. Roughly six categories dominate: **web-scraped**,
**satellite**, **transaction**, **sentiment**, **geolocation**, and **IoT**.

Two figures worth knowing before you go shopping:

- The market reached roughly **$13.6bn in 2025**, growing about 28% year on year
- **Web-scraped data is the largest single category**, around 15% of spend, and
  the fastest growing, because extraction costs have collapsed while update
  frequency has risen to daily or hourly

Adoption is no longer a differentiator in itself. Over 90% of systematic funds
and more than 60% of fundamental long/short funds use at least one alternative
dataset. The edge is in selection, integration speed, and having history nobody
else bothered to collect.

---

## Contents

- [How to evaluate a dataset](#how-to-evaluate-a-dataset)
- [Web-scraped data](#web-scraped-data)
- [Property and real estate](#property-and-real-estate)
- [Satellite and geospatial](#satellite-and-geospatial)
- [Transaction and card data](#transaction-and-card-data)
- [Sentiment, news, and social](#sentiment-news-and-social)
- [Geolocation and foot traffic](#geolocation-and-foot-traffic)
- [App and web analytics](#app-and-web-analytics)
- [Supply chain and trade](#supply-chain-and-trade)
- [ESG and climate](#esg-and-climate)
- [Free and open sources](#free-and-open-sources)
- [Marketplaces and aggregators](#marketplaces-and-aggregators)
- [Tools and infrastructure](#tools-and-infrastructure)
- [Compliance and legal](#compliance-and-legal)
- [Reading](#reading)
- [Contributing](#contributing)

---

## How to evaluate a dataset

The questions that separate a usable dataset from an expensive disappointment.

**How long is the history?** A signal you cannot backtest is a signal you cannot
size. Two years is usually the minimum for anything seasonal; five is better.
Many vendors sell an impressive live feed with almost no history behind it.

**Is it point-in-time?** If the vendor restates past values, your backtest is
contaminated by information that did not exist at the time. Ask explicitly
whether the history is point-in-time or as-restated. This single question kills
a lot of deals.

**What is the panel bias?** Card transaction panels skew to particular
demographics and card issuers. App panels skew to opt-in users. Web-scraped
prices skew to whatever the site shows an anonymous visitor. None of these are
disqualifying, all of them need to be understood before you attribute a move to
the underlying company rather than to the panel.

**What is the lag?** Daily data delivered eleven days later is monthly data.

**Can you map it to securities?** A dataset about "Tesco" is only useful if you
can join it to a ticker, and consistently, through renames and restructures.
Entity resolution is usually the largest hidden integration cost.

**How many other people have it?** Widely licensed datasets get arbitraged away.
Ask about the client count in your strategy category. Vendors rarely volunteer
it and will often answer if asked directly.

**What happens when the source changes?** Websites redesign, apps change their
APIs, satellites get retired. Ask how the vendor has handled past breaks, and
whether they backfill or leave a gap.

---

## Web-scraped data

The largest and fastest-growing category. Job postings, pricing, product
catalogues, listings, reviews, and corporate sites.

### Providers

- [Thinknum](https://www.thinknum.com/) - Web-scraped job postings, product pricing, store locations, and social metrics, mapped to tickers. One of the longest-running vendors in this category.
- [YipitData](https://www.yipitdata.com/) - Web and transaction data with heavy analyst overlay. Sells research conclusions as much as raw data.
- [M Science](https://mscience.com/) - Transaction and web data with sector research.
- [Similarweb](https://www.similarweb.com/corp/developers/) - Web traffic and engagement estimates. Publicly listed, and one of the few alt data vendors you can also analyse as a company.
- [Bright Data](https://brightdata.com/) - Infrastructure plus pre-built datasets across ecommerce, social, and business listings. Buy the data or run your own collection.
- [Apify](https://apify.com/store) - Marketplace of scrapers and datasets. The cheapest route to a proof of concept before committing to a vendor.
- [Oxylabs](https://oxylabs.io/) - Scraping infrastructure and ready-made datasets.
- [Zyte](https://www.zyte.com/) - Scraping infrastructure with managed extraction services.
- [Kadoa](https://www.kadoa.com/) - AI-driven extraction that adapts to site changes automatically.

### Retail and consumer

- [Happy Endpoint](https://happyendpoint.com/library) - Real-time APIs and bulk snapshots for retail and property portals: Tesco, IKEA, Sephora, H&M, Kohl's, Klarna, and others. Self-serve with free tiers, which makes it usable for research before a procurement cycle.
- [Rainforest API](https://www.rainforestapi.com/) - Amazon product, pricing, and review data.
- [Keepa](https://keepa.com/#!api) - Amazon price history going back years. Notable because the history genuinely exists, unlike most price datasets.

---

## Property and real estate

Underused as alternative data, and directly relevant to REITs, homebuilders,
mortgage originators, building materials, and regional banks.

- [Happy Endpoint property APIs](https://happyendpoint.com/library) - Listings, agents, off-plan supply, and transaction history across the UAE, UK, Spain, Turkey, Singapore, Japan, and the US. Useful for tracking supply and asking-price momentum at community level.
- [HM Land Registry Price Paid](https://landregistry.data.gov.uk/app/ppd/) - **Free.** Every registered residential sale in England and Wales since 1995. Complete, authoritative, point-in-time by construction.
- [Dubai Pulse DLD transactions](https://www.dubaipulse.gov.ae/data/dld-transactions/dld_transactions-open) - **Free.** Full Dubai transaction history, one of the most transparent property markets for data.
- [ATTOM Data](https://www.attomdata.com/) - US property, deed, mortgage, and foreclosure records.
- [CoreLogic](https://www.corelogic.com/) - US property records, AVMs, and mortgage risk.
- [awesome-real-estate-apis](https://github.com/happyendpointhq/awesome-real-estate-apis) - Fuller list of property data sources by country.

Listing counts and days-on-market often turn before transaction prices do, which
is what makes listings interesting as a leading indicator rather than merely a
description of the market.

---

## Satellite and geospatial

Expensive, and the classic alt data category. Institutional pricing commonly
runs from tens of thousands to several hundred thousand a year.

- [Planet Labs](https://www.planet.com/) - Daily global imagery. Publicly listed.
- [Orbital Insight](https://orbitalinsight.com/) - Geospatial analytics over imagery and location data.
- [SpaceKnow](https://www.spaceknow.com/) - Satellite analytics with published economic indices.
- [RS Metrics](https://rsmetrics.com/) - Metals, parking lots, and industrial activity.
- [ICEYE](https://www.iceye.com/) - Radar imaging, which sees through cloud and at night. Materially different coverage profile to optical.
- [Sentinel Hub](https://www.sentinel-hub.com/) - Commercial access layer over free ESA Sentinel data. A far cheaper entry point.
- [Copernicus Open Access Hub](https://dataspace.copernicus.eu/) - **Free.** ESA Sentinel imagery. Genuinely free, genuinely good, and the right place to prototype before paying anyone.
- [NASA Earthdata](https://www.earthdata.nasa.gov/) - **Free.** Decades of Earth observation data.
- [USGS EarthExplorer](https://earthexplorer.usgs.gov/) - **Free.** Landsat archive going back to the 1970s.

If you are new to this category, build your first prototype on Copernicus and
Landsat. The free archives are deep enough to prove or kill most theses before
you spend anything.

---

## Transaction and card data

Consumer spending, from card panels, receipts, and bank feeds. Powerful for
revenue nowcasting, and the category with the most acute panel bias questions.

- [Earnest Analytics](https://www.earnestanalytics.com/) - US card and transaction panels.
- [Consumer Edge](https://consumer-edge.com/) - Transaction data across US and international panels.
- [Facteus](https://www.facteus.com/) - Synthetic and anonymised transaction data.
- [Second Measure (Bloomberg)](https://secondmeasure.com/) - Card transaction analytics.
- [Fable Data](https://fabledata.com/) - European transaction data, a region less covered than the US.
- [Plaid](https://plaid.com/) - Bank account connectivity. Fintech infrastructure rather than a research panel, but occasionally used as one.

Always ask what share of the merchant's actual revenue the panel represents, and
whether that share is stable over time. A panel that drifts will manufacture
growth that is not there.

---

## Sentiment, news, and social

- [RavenPack](https://www.ravenpack.com/) - News analytics and sentiment, long established in systematic strategies.
- [Brandwatch](https://www.brandwatch.com/) - Social listening.
- [StockTwits API](https://api.stocktwits.com/developers/docs) - Retail investor sentiment, free tier available.
- [Reddit API](https://www.reddit.com/dev/api/) - Retail sentiment. Terms and pricing changed substantially in 2023; check current commercial terms.
- [GDELT Project](https://www.gdeltproject.org/) - **Free.** Global news events, tone, and themes, updated every fifteen minutes. Extraordinary value for zero cost, and consistently underused.
- [Alpha Vantage News Sentiment](https://www.alphavantage.co/documentation/) - Free tier with news sentiment attached to tickers.

---

## Geolocation and foot traffic

- [Placer.ai](https://www.placer.ai/) - Foot traffic to physical locations. Widely used for retail and REIT analysis.
- [Advan Research](https://advanresearch.com/) - Foot traffic and mobility.
- [Veraset](https://www.veraset.com/) - Raw movement data.
- [SafeGraph](https://www.safegraph.com/) - Points of interest and place data.
- [Unacast](https://www.unacast.com/) - Human mobility data.

This category carries the heaviest privacy scrutiny. Regulatory attitudes to
location data have hardened considerably, and vendor practices vary widely. Do
real diligence on consent chains here, not just on data quality.

---

## App and web analytics

- [Sensor Tower](https://sensortower.com/) - App downloads, revenue, and usage estimates.
- [data.ai](https://www.data.ai/) - App market data, formerly App Annie.
- [Similarweb](https://www.similarweb.com/corp/developers/) - Website traffic and engagement.
- [Semrush](https://www.semrush.com/api-documentation/) - Search visibility, keyword rankings, and advertising spend estimates. A reasonable proxy for marketing intensity.
- [Apptopia](https://apptopia.com/) - Mobile app performance data.

---

## Supply chain and trade

- [ImportGenius](https://www.importgenius.com/) - US customs and bill of lading records.
- [Panjiva (S&P Global)](https://panjiva.com/) - Global trade and shipping data.
- [MarineTraffic](https://www.marinetraffic.com/en/ais-api-services) - AIS vessel tracking. Free tier available.
- [FlightAware](https://www.flightaware.com/commercial/aeroapi/) - Flight tracking.
- [UN Comtrade](https://comtradeplus.un.org/) - **Free.** Offici