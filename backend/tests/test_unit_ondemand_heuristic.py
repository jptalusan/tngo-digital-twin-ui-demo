from app.services import ondemand as ondemand_service


def test_insertion_selects_feasible_vehicle():
    vehicles = [
        ondemand_service.VehicleState(vehicle_id="veh-1", capacity=2, route=[]),
        ondemand_service.VehicleState(vehicle_id="veh-2", capacity=4, route=[]),
    ]
    request = ondemand_service.Request(
        request_id="req-1",
        origin_lat=35.0,
        origin_lon=-90.0,
        destination_lat=35.01,
        destination_lon=-90.01,
        passengers=3,
        pickup_window=ondemand_service.TimeWindow(480, 520),
        dropoff_window=ondemand_service.TimeWindow(480, 600),
    )

    result = ondemand_service.find_best_insertion(vehicles, request, start_min=480)
    assert result is not None
    assert result.vehicle_id == "veh-2"
    assert result.eta_minutes >= 0


def test_insertion_respects_time_windows():
    vehicles = [ondemand_service.VehicleState(vehicle_id="veh-1", capacity=4, route=[])]
    request = ondemand_service.Request(
        request_id="req-2",
        origin_lat=35.0,
        origin_lon=-90.0,
        destination_lat=36.0,
        destination_lon=-91.0,
        passengers=1,
        pickup_window=ondemand_service.TimeWindow(480, 481),
        dropoff_window=ondemand_service.TimeWindow(480, 481),
    )

    result = ondemand_service.find_best_insertion(vehicles, request, start_min=480)
    assert result is None
