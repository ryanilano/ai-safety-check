# ADR-001: Use TheLook E-Commerce for Customer Intelligence

**Date:** 2026-06-25
**Status:** Accepted

## Context

Two databases were available for the Customer Experience Agent:
- **TheLook E-Commerce** (BigQuery): USERS, EVENTS, ORDERS, ORDER_ITEMS, PRODUCTS, INVENTORY_ITEMS, DISTRIBUTION_CENTERS
- **Brazilian E-Commerce** (BigQuery): OLIST_CUSTOMERS, OLIST_ORDERS, OLIST_ORDER_ITEMS, OLIST_PRODUCTS, OLIST_ORDER_REVIEWS, OLIST_ORDER_PAYMENTS

The agent requires: customer demographics, purchase history, behavioral events, and product catalog with pricing and margin data.

## Decision

Use **TheLook E-Commerce** as the primary database. Use Brazilian E-Commerce as a secondary reference if cross-validation is needed in future iterations.

## Consequences

**Positive:**
- TheLook has an EVENTS table with granular behavioral signals (page views, cart additions, purchases) — essential for the behavioral analysis node
- INVENTORY_ITEMS includes cost AND retail_price, enabling margin calculation for offer targeting
- USERS table has traffic_source, enabling acquisition channel analysis
- All tables join cleanly on user_id and product_id

**Negative / Trade-offs:**
- Brazilian E-Commerce has OLIST_ORDER_REVIEWS (customer satisfaction scores) which TheLook lacks — NPS-style analysis is not possible
- TheLook has no loyalty tier data or points balance

**Neutral:**
- Both databases use the same CRAFT MCP platform, so switching later is a config-only change
