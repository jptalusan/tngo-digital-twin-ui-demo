# API Examples (Memphis Service Zone)

These examples target the default Memphis downtown service zone and assume:
- API is running on `http://localhost:8000`
- `API_PREFIX=/api`

## Health

```bash
curl http://localhost:8000/api/health
```

## Autocomplete

```bash
curl "http://localhost:8000/api/autocomplete?query=Memphis"
```

## Nearest stops

```bash
curl -X POST http://localhost:8000/api/nearest-stops \
  -H "Content-Type: application/json" \
  -d '{
    "coordinates": [35.1495, -90.0490],
    "max_distance_m": 2000,
    "limit": 5
  }'
```

## Fixed-line (depart_at)

```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.10207407719635, -90.03855626703466],
    "destination": [35.15419142334027, -89.9346853715579],
    "depart_at_min": 480,
    "service_date": "20250101",
    "transfer_limit": 3,
    "max_walk_meters": 2000,
    "max_wait_minutes": 60,
    "max_invehicle_minutes": 180,
    "max_total_minutes": 240
  }'
```

## Fixed-line (arrive_by)

```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.10207407719635, -90.03855626703466],
    "destination": [35.15419142334027, -89.9346853715579],
    "arrive_by_min": 540,
    "transfer_limit": 3,
    "service_date": "20250101"
  }'
```

## On-demand (insertion updates vehicle schedule)
Call twice to see the active route update with the new request insertion.

```bash
curl -X POST http://localhost:8000/api/plan/on-demand \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.10207407719635, -90.03855626703466],
    "destination": [35.15419142334027, -89.9346853715579],
    "pickup_window_start_min": 480,
    "pickup_window_end_min": 520,
    "dropoff_window_end_min": 600,
    "passengers": 1
  }'
```

```bash
curl -X POST http://localhost:8000/api/plan/on-demand \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.1520, -90.0550],
    "destination": [35.1600, -90.0700],
    "pickup_window_start_min": 340,
    "pickup_window_end_min": 540,
    "dropoff_window_end_min": 760,
    "passengers": 1
  }'
```

### For west memphis (continuation)
```bash
curl -X POST http://localhost:8000/api/plan/on-demand \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.05824679207186, -90.07969506176909],
    "destination": [35.08693080695092, -90.06654279675395],
    "pickup_window_start_min": 340,
    "pickup_window_end_min": 540,
    "dropoff_window_end_min": 760,
    "passengers": 1
  }'
```

## On-demand schedule evaluation
```bash
curl -X POST http://localhost:8000/api/on-demand/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": "veh-001"
  }'
```

## On-demand fulfillment summary
```bash
curl -X POST http://localhost:8000/api/on-demand/fulfillment \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": "veh-001"
  }'
```

## On-demand summary (all requests)
```bash
curl http://localhost:8000/api/on-demand/summary
```

## On-demand route manifest (OSRM)
```bash
curl -X POST http://localhost:8000/api/on-demand/manifest \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": "veh-001"
  }'
```

## Private vehicle (point-to-point)
```bash
curl -X POST http://localhost:8000/api/plan/private-vehicle \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.10207407719635, -90.03855626703466],
    "destination": [35.15419142334027, -89.9346853715579]
  }'
```

## Multimodal (compare fixed-line, on-demand, multimodal)

```bash
curl -X POST http://localhost:8000/api/plan/multimodal \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.10207407719635, -90.03855626703466],
    "destination": [35.15419142334027, -89.9346853715579],
    "depart_at_min": 480,
    "pickup_window_start_min": 380,
    "pickup_window_end_min": 520,
    "dropoff_window_end_min": 1000,
    "service_date": "20250101",
    "transfer_limit": 5
  }'
```

## Reverse geocode (mock)

```bash
curl -X POST http://localhost:8000/api/reverse-geocode \
  -H "Content-Type: application/json" \
  -d '{
    "coordinates": [35.1495, -90.0490]
  }'
```

## Long distance Shelby (Memphis) to Stanton (BOC)
```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.1495, -90.0490],
    "destination": [35.40167589770319, -89.4152679475825],
    "depart_at_min": 480,
    "service_date": "20251001",
    "transfer_limit": 3,
    "boc_request": true
  }'
```

## Long distance Jackson to Stanton
```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.61840705868092, -88.82546943674076],
    "destination": [35.40167589770319, -89.4152679475825],
    "depart_at_min": 480,
    "service_date": "20251001",
    "transfer_limit": 3,
    "boc_request": true
  }'
```


## Long distance Stanton to Jackson (Reverse)
```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.40167589770319, -89.4152679475825],
    "destination": [35.61840705868092, -88.82546943674076],
    "depart_at_min": 480,
    "service_date": "20251001",
    "transfer_limit": 3,
    "boc_request": true
  }'
```


## Long distance Jackson to Stanton
```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.61840705868092, -88.82546943674076],
    "destination": [35.66060406006281, -88.8409528070227],
    "depart_at_min": 480,
    "service_date": "20251001",
    "transfer_limit": 3,
    "boc_request": false
  }'
```
