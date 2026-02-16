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

## Fixed-line (depart_at)

```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.1495, -90.0490],
    "destination": [35.1505, -90.0480],
    "depart_at_min": 480,
    "service_date": "20250101",
    "transfer_limit": 1
  }'
```

## Fixed-line (arrive_by)

```bash
curl -X POST http://localhost:8000/api/plan/fixed-line \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.1495, -90.0490],
    "destination": [35.1505, -90.0480],
    "arrive_by_min": 540,
    "service_date": "20250101"
  }'
```

## On-demand (single request)

```bash
curl -X POST http://localhost:8000/api/plan/on-demand \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.1495, -90.0490],
    "destination": [35.1505, -90.0480],
    "passengers": 1,
    "pickup_window_start_min": 480,
    "pickup_window_end_min": 520,
    "dropoff_window_end_min": 600
  }'
```

## Multimodal (compare fixed-line, on-demand, multimodal)

```bash
curl -X POST http://localhost:8000/api/plan/multimodal \
  -H "Content-Type: application/json" \
  -d '{
    "origin": [35.1495, -90.0490],
    "destination": [35.1505, -90.0480],
    "depart_at_min": 480,
    "service_date": "20250101",
    "transfer_limit": 1
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
