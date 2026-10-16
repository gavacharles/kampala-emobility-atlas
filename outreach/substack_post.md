# Kampala's electric motorcycle boom has a geography problem

*Where electric bodas and electric cars can take hold, where their stations should go, and who gets left out. A map built entirely from open data.*

**Interactive atlas:** https://gavacharles.github.io/kampala-emobility-atlas/
**Code and data:** https://github.com/gavacharles/kampala-emobility-atlas

---

Stand at any junction in Kampala and count the boda-bodas. Greater Kampala has more than 400,000 motorcycles, and the city runs on them. Over the past two years, a quiet change has started under the seat: Uganda's battery-swapping network more than doubled, from about 150 stations in mid-2024 to over 350 by late 2025, according to the World Bank. Riders pull into a forecourt, hand over a flat battery, take a charged one and ride off.

Electric cars are a different story. Uganda imported only 17 fully electric cars between 2022 and April 2024. The first public fast charger in Kampala is a pilot.

I wanted to answer three questions that matter to riders, investors and city planners, using only data anyone can download:

1. Where in Greater Kampala are electric bodas and electric cars most likely to take hold?
2. Where should swap stations and fast chargers go?
3. Who would those networks actually serve?

## What I built

I divided Greater Kampala into 3,248 one-kilometre squares and scored the 1,968 with people or activity in them, home to about 6.45 million residents. For each square I brought together:

- **Roads, shops, markets, boda stages, fuel stations and banks** from OpenStreetMap, including 15,868 km of road for measuring distances along streets, not as the crow flies.
- **Population in 2020, 2025 and 2030** from WorldPop.
- **1.2 million building outlines** from Microsoft's satellite-derived footprints, used to estimate housing wealth and who can charge a car at home.
- **A Sentinel-2 satellite image** from 29 June 2026 and a **30 m elevation model**, used to check every proposed site for slopes, flood-prone valley floors and wetlands.

![The proposed networks on Sentinel-2 imagery](../figures/gis01_satellite_proposed_networks.png)

## Finding 1: the boda belt and the car core

Suitability for electric bodas is concentrated in a dense band running from Bwaise and Kawempe south through Mulago, Wandegeya and Kisenyi to Katwe and Kibuye. Electric-car suitability peaks in the CBD, Nakasero, Kololo and Kamwokya. The patterns are strongly clustered and line up with the built-up surface you can see from space.

I didn't trust my own weights, so I re-ran the scoring 1,000 times with randomly shifted weights. 163 squares stayed in the top 10% for e-bodas almost every time. Those are the safe bets.

## Finding 2: put the swap stations at petrol stations

I let a computer add swap stations one at a time, each time choosing the spot that brings the most uncovered riders within 2.5 km by road. Ten stations reach 28% of e-boda demand, 30 reach 55% and 60 reach 75%. That's about double what random placement achieves, and within 3 percentage points of the mathematically best possible network.

![Building the swap network one site at a time](../figures/anim_network_buildout.gif)

Two things surprised me. First, **53 of the 60 best sites are petrol stations**. Restricting the network to fuel forecourts costs only about one percentage point of coverage, which is good news for operators partnering with oil marketers. Second, for cars, **10 fast chargers reach 62% of e-car demand** within 5 km, because that demand is concentrated in a small, affluent core.

## Finding 3: the grid, not the map, is the bottleneck

A network designed to be within reach of most riders concentrates a lot of power at a few places. If a quarter of Kampala's motorcycles went electric, the 60 stations would handle about 72,000 swaps a day and need around 17.5 MW at peak. Twenty-one of them would need a medium-voltage grid connection, not just a transformer. Coverage and capacity are different problems.

## Finding 4: the saving is real, if a station is near you

A rider with a swap station on their route saves about **UGX 5,900 a day** going electric, at today's petrol price of around UGX 6,650 a litre. That held in every one of 5,000 simulations with different fuel prices, swap prices, distances and maintenance costs.

But riders have to get to the station. Measured from where people live:

- With **10** stations, the average rider saves about **UGX 2,000** a day.
- With **30**, about **UGX 3,850**.
- With **60**, about **UGX 4,500**.

![Coverage and saving by distance from the CBD](../figures/fig07_access_by_ring.png)

At the edge of the city it's starker. More than 20 km from the centre, a rider would **lose** about UGX 3,550 a day with only 10 stations, because of the trips to swap. With 60 stations, they gain about UGX 2,200. The outer rings are also where 55% of new residents are settling.

## Finding 5: electric cars should start with taxis

For a ride-hail or taxi car doing 180 km a day, an electric car repays a UGX 12 million price premium in about **8 months**, and comes out ahead over five years in 96% of simulations. For a private car doing 40 km a day, it's a coin flip: about **52%**. The deciding factors are the purchase price, which a 25% import duty pushes up, and whether you can charge at home, which is far more common in the wealthiest neighbourhoods.

## Who gets left out?

In rich countries, charging stations tend to cluster in wealthy areas. In Kampala, the swap network does the opposite: it reaches the least-wealthy fifth of residents better (54% covered) than the wealthiest (33%), because that's where boda demand is. The real divide is geographic. Within 5 km of the centre, 93% of people are covered by 30 swap stations. Beyond 20 km, 11%.

## What this means

- **Operators:** start at the inner-city forecourts, then densify outwards in clusters. A single station in a peri-urban area doesn't make riders better off.
- **Utilities and planners:** expect clustered medium-voltage requests along a handful of corridors as adoption grows.
- **Policymakers:** support peri-urban stations, where commercial networks arrive last, and target car incentives at taxi and ride-hail fleets first.

## What this can't tell you

This is built from public data, not operator records. Scores show where conditions are favourable, not where people have already switched. Several cost inputs are assumptions and are labelled as such. Only three swap stations are mapped in OpenStreetMap, so I designed the network from scratch rather than auditing the real one. If you run a swap network, finance riders, or work at a utility and want to test these results against real data, I'd like to hear from you.

Everything is open: the code, the maps and the data are on GitHub, and you can explore the interactive atlas, play the network build-out and test your own fuel and swap prices.

*Two research papers based on this work are in preparation.*
