from truepresence.adapters.telegram_bot import get_service_for_tenant


def test_get_service_for_tenant_is_stable_per_tenant() -> None:
    svc_a1 = get_service_for_tenant("tenant-a")
    svc_a2 = get_service_for_tenant("tenant-a")
    svc_b = get_service_for_tenant("tenant-b")

    assert svc_a1 is svc_a2
    assert svc_a1 is not svc_b
    assert svc_a1.tenant_id == "tenant-a"
    assert svc_b.tenant_id == "tenant-b"
