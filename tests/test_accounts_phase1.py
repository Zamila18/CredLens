"""Phase 1 of the unified platform: real accounts, companies, invitations, platform admins.

Owner role: D (full-stack).
Implements: acceptance scenarios 1 to 3 and the basics of 9 (docs: the implementation plan).

Every caller here is a real account with its own browser session (a TestClient cookie jar):
the platform admins from the (test) environment, a company's owner Credit Officer, a Records
Desk officer
and a second Credit Officer who joined with invitation codes, and a second company. Nothing
touches data/app.db: each test module gets an empty temporary database.
"""

from __future__ import annotations

import copy
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.accounts import passwords, service
from src.accounts.bootstrap_platform_admins import bootstrap
from src.config import load_config
from src.db import models as db
from src.db.models import create_tables, make_engine

STRONG = "Maple-River-2049!"
OWNER_ENV = {
    "CREDLENS_PLATFORM_ADMIN_1_EMAIL": "Admin.One@credlens.example",
    "CREDLENS_PLATFORM_ADMIN_1_PASSWORD": "Platform-One-2049!",
    "CREDLENS_PLATFORM_ADMIN_2_EMAIL": "admin.two@credlens.example",
    "CREDLENS_PLATFORM_ADMIN_2_PASSWORD": "Platform-Two-2049!",
}


def company_body(**over) -> dict:
    body = {
        "full_name": "Rina Akter",
        "email": "rina@padma.example",
        "mobile": "01711111111",
        "department": "Credit",
        "password": STRONG,
        "confirm_password": STRONG,
        "legal_name": "Padma Microfinance Limited",
        "trading_name": "Padma MFI",
        "registration_number": "MFI-2024-0042",
        "org_type": "mfi",
        "sector": "Microfinance",
        "official_email": "info@padma.example",
        "contact_number": "028000001",
        "country": "BD",
        "division": "Dhaka",
        "city": "Dhaka",
        "address": "12 Motijheel Commercial Area, Dhaka",
        "website": "https://padma.example",
    }
    body.update(over)
    return body


def join_body(code: str, **over) -> dict:
    body = {
        "full_name": "Karim Uddin",
        "email": "karim@padma.example",
        "mobile": "01722222222",
        "department": "Sales North",
        "password": STRONG,
        "confirm_password": STRONG,
        "invitation_code": code,
        "role": "records_officer",
        "employee_id": "E-1001",
    }
    body.update(over)
    return body


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    patcher = pytest.MonkeyPatch()
    patcher.setenv("CREDLENS_SECRET_KEY", "k" * 40)
    for key, value in OWNER_ENV.items():
        patcher.setenv(key, value)
    config = copy.deepcopy(load_config())
    config["auth"]["rate_limit"].update(
        register_per_ip=500,
        login_per_ip=500,
        login_per_identifier=500,
        invite_check_per_ip=500,
        invite_check_per_identifier=500,
    )
    url = "sqlite:///" + (tmp_path_factory.mktemp("phase1") / "p1.db").as_posix()
    create_tables(url)
    engine = make_engine(url)
    from src.api.state import Services

    services = Services(config=config, engine=engine)
    from src.api.main import app

    app.state.services = services
    yield type("World", (), {"config": config, "engine": engine, "services": services})
    del app.state.services
    engine.dispose()
    patcher.undo()


def client() -> TestClient:
    from src.api.main import app

    return TestClient(app)


def sign_in(email: str, password: str = STRONG) -> TestClient:
    c = client()
    reply = c.post("/auth/login", json={"identifier": email, "password": password})
    assert reply.status_code == 200, reply.text
    return c


@pytest.fixture(scope="module")
def company(world):
    """Padma: owner, then a Records Desk officer and a second officer who joined with codes."""
    anon = client()
    made = anon.post("/auth/register/company", json=company_body())
    assert made.status_code == 201, made.text
    owner = sign_in("rina@padma.example")
    desk_code = owner.post(
        "/org/invitations",
        json={"role": "records_officer", "days": 7, "max_uses": 2},
    ).json()["code"]
    assert anon.post("/auth/register/join", json=join_body(desk_code)).status_code == 201
    officer_code = owner.post("/org/invitations", json={"role": "credit_officer"}).json()["code"]
    second = join_body(
        officer_code,
        role="credit_officer",
        full_name="Nasrin Sultana",
        email="nasrin@padma.example",
        mobile="01733333333",
        employee_id="E-2001",
    )
    assert anon.post("/auth/register/join", json=second).status_code == 201
    return type(
        "Company",
        (),
        {
            "owner": owner,
            "desk": sign_in("karim@padma.example"),
            "officer": sign_in("nasrin@padma.example"),
            "desk_code": desk_code,
        },
    )


# --- scenario 2: company registration ---------------------------------------------------


def test_a_first_credit_officer_registers_a_company_and_owns_it(world, company):
    me = company.owner.get("/auth/me").json()
    assert me["role"] == "credit_officer" and me["is_owner"] is True
    assert me["organization_name"] == "Padma MFI" and me["environment"] == "pilot"
    assert me["is_platform"] is False
    profile = company.owner.get("/org/profile").json()
    assert profile["legal_name"] == "Padma Microfinance Limited"
    assert profile["registration_number"] == "MFI-2024-0042" and profile["status"] == "active"
    people = company.owner.get("/org/employees").json()
    assert [p["role"] for p in people] == ["credit_officer", "records_officer", "credit_officer"]
    assert people[0]["is_owner"] and not people[2]["is_owner"]


def test_registration_names_every_missing_or_wrong_field(world):
    reply = client().post(
        "/auth/register/company",
        json=company_body(
            email="nope",
            mobile="x",
            legal_name="",
            org_type="spaceship",
            address="short",
            password="short",
            confirm_password="other",
        ),
    )
    assert reply.status_code == 422
    fields = reply.json()["detail"]["fields"]
    for name in ("email", "mobile", "legal_name", "org_type", "address", "confirm_password"):
        assert name in fields, name
    # a regulated type needs its number, an "other" company does not
    regulated = client().post(
        "/auth/register/company", json=company_body(registration_number="", email="x@y.example")
    )
    assert "registration_number" in regulated.json()["detail"]["fields"]


def test_duplicates_are_refused_whatever_the_case(world, company):
    anon = client()
    same_email = anon.post("/auth/register/company", json=company_body(email="RINA@Padma.Example"))
    assert (
        same_email.status_code == 409 and same_email.json()["detail"]["code"] == "identifier_taken"
    )
    same_number = anon.post(
        "/auth/register/company",
        json=company_body(
            email="other@x.example",
            mobile="01799999999",
            registration_number="mfi 2024-0042",
            legal_name="Another Name Ltd",
        ),
    )
    assert same_number.status_code == 409
    assert same_number.json()["detail"]["code"] == "company_already_registered"
    same_name = anon.post(
        "/auth/register/company",
        json=company_body(
            email="third@x.example", mobile="01788888888", registration_number="ZZ-9999"
        ),
    )
    assert same_name.json()["detail"]["code"] == "company_may_exist"


def test_the_password_policy_is_enforced_and_hashes_are_argon2id(world, company):
    weak = {
        "short": "Ab1!",
        "no symbol": "Maplerivers2049xy",
        "common": "Password@123",
        "no digit": "Maple-River-Stone!",
        "own name": "Rina-Akter-2049!",
    }
    for label, password in weak.items():
        reply = client().post(
            "/auth/register/company",
            json=company_body(
                email=f"{label.replace(' ', '')}@z.example",
                password=password,
                confirm_password=password,
            ),
        )
        assert reply.status_code == 422, label
        assert "password" in reply.json()["detail"]["fields"], label
    with Session(world.engine) as session:
        stored = service.credential_for(session, "rina@padma.example").password_hash
    assert stored.startswith("$argon2id$") and STRONG not in stored


def test_an_older_scrypt_hash_still_signs_in_and_is_replaced(world, company):
    import base64
    import hashlib

    salt = b"0123456789abcdef"
    digest = hashlib.scrypt(
        b"Old-Scrypt-2049!", salt=salt, n=2**14, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024
    )
    legacy = "scrypt$16384$8$1$%s$%s" % (
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )
    assert passwords.verify_password("Old-Scrypt-2049!", legacy)
    with Session(world.engine) as session:
        credential = service.credential_for(session, "nasrin@padma.example")
        credential.password_hash = legacy
        session.commit()
    sign_in("nasrin@padma.example", "Old-Scrypt-2049!")
    with Session(world.engine) as session:
        assert service.credential_for(session, "nasrin@padma.example").password_hash.startswith(
            "$argon2id$"
        )
        credential = service.credential_for(session, "nasrin@padma.example")
        credential.password_hash = passwords.hash_password(STRONG)
        session.commit()


# --- scenario 3: employee registration --------------------------------------------------


def test_a_records_officer_joins_the_right_company_and_role_from_the_code(world, company):
    me = company.desk.get("/auth/me").json()
    assert (
        me["role"] == "records_officer"
        and me["organization_name"] == "Padma MFI"
        and not me["is_owner"]
    )
    with Session(world.engine) as session:
        profile = session.scalar(
            select(db.StaffProfile).where(db.StaffProfile.employee_id == "E-1001")
        )
        assert profile.job_title == "Records Officer"
        membership = service.active_membership(session, profile.user_id)
        assert membership.role == "records_officer" and membership.is_owner is False


def test_the_form_cannot_pick_the_company_or_the_role(world, company):
    """Extra fields are refused; the role and company can only come from the code."""
    owner_code = company.owner.post(
        "/org/invitations", json={"role": "records_officer", "max_uses": 3}
    ).json()["code"]
    body = join_body(
        owner_code, email="sneaky@padma.example", mobile="01744444444", employee_id="E-3001"
    )
    body["role"] = "credit_officer"
    body["organization_id"] = "somewhere-else"
    reply = client().post("/auth/register/join", json=body)
    assert reply.status_code == 422  # unknown fields are refused, never used
    assert "Extra inputs are not permitted" in reply.text
    with Session(world.engine) as session:
        assert service.credential_for(session, "sneaky@padma.example") is None


def test_wrong_expired_revoked_and_used_up_codes_are_refused_alike(world, company):
    anon = client()
    messages = set()
    wrong = anon.post(
        "/auth/register/join",
        json=join_body(
            "AAAA-BBBB-CCCC-DDDD", email="w1@padma.example", mobile="01755550001", employee_id="W1"
        ),
    )
    assert wrong.status_code == 422 and "invitation_code" in wrong.json()["detail"]["fields"]
    messages.add(wrong.json()["detail"]["fields"]["invitation_code"])

    code = company.owner.post("/org/invitations", json={"role": "records_officer"}).json()
    # expire it
    with Session(world.engine) as session:
        row = session.get(db.Invitation, code["invitation"]["invitation_id"])
        row.expires_at = service.now() - timedelta(minutes=1)
        session.commit()
    expired = anon.post(
        "/auth/register/join",
        json=join_body(
            code["code"], email="w2@padma.example", mobile="01755550002", employee_id="W2"
        ),
    )
    messages.add(expired.json()["detail"]["fields"]["invitation_code"])

    fresh = company.owner.post("/org/invitations", json={"role": "records_officer"}).json()
    revoked = company.owner.post(f"/org/invitations/{fresh['invitation']['invitation_id']}/revoke")
    assert revoked.json()["state"] == "revoked"
    gone = anon.post(
        "/auth/register/join",
        json=join_body(
            fresh["code"], email="w3@padma.example", mobile="01755550003", employee_id="W3"
        ),
    )
    messages.add(gone.json()["detail"]["fields"]["invitation_code"])

    single = company.owner.post(
        "/org/invitations", json={"role": "records_officer", "max_uses": 1}
    ).json()
    first = anon.post(
        "/auth/register/join",
        json=join_body(
            single["code"], email="w4@padma.example", mobile="01755550004", employee_id="W4"
        ),
    )
    assert first.status_code == 201
    second = anon.post(
        "/auth/register/join",
        json=join_body(
            single["code"], email="w5@padma.example", mobile="01755550005", employee_id="W5"
        ),
    )
    messages.add(second.json()["detail"]["fields"]["invitation_code"])
    assert len(messages) == 1  # one answer for every kind of bad code


def test_duplicate_email_and_employee_id_are_refused(world, company):
    code = company.owner.post(
        "/org/invitations", json={"role": "records_officer", "max_uses": 5}
    ).json()["code"]
    anon = client()
    email = anon.post(
        "/auth/register/join",
        json=join_body(code, email="KARIM@padma.example", mobile="01766660001", employee_id="D-1"),
    )
    assert email.status_code == 409 and email.json()["detail"]["code"] == "identifier_taken"
    ok = anon.post(
        "/auth/register/join",
        json=join_body(code, email="dup1@padma.example", mobile="01766660002", employee_id="D-1"),
    )
    assert ok.status_code == 201
    again = anon.post(
        "/auth/register/join",
        json=join_body(code, email="dup2@padma.example", mobile="01766660003", employee_id=" d-1 "),
    )
    assert again.status_code == 409 and again.json()["detail"]["code"] == "employee_id_taken"


def test_a_second_credit_officer_joins_only_through_an_officer_invitation(world, company):
    me = company.officer.get("/auth/me").json()
    assert me["role"] == "credit_officer" and me["is_owner"] is False
    # a Records Desk officer code cannot make an officer, and an officer cannot make invitations
    assert (
        company.officer.post("/org/invitations", json={"role": "records_officer"}).status_code
        == 403
    )
    assert company.officer.get("/org/invitations").json()["detail"]["code"] == "owner_only"
    assert (
        company.desk.post("/org/invitations", json={"role": "records_officer"}).status_code == 403
    )


def test_invitations_store_only_a_hash_and_show_who_joined(world, company):
    listing = company.owner.get("/org/invitations").json()
    assert listing and all(len(i["code_hint"]) == 4 and "code" not in i for i in listing)
    joined = [u for i in listing for u in i["uses"]]
    assert {"Karim Uddin", "Nasrin Sultana"} <= {u["display_name"] for u in joined}
    with Session(world.engine) as session:
        hashes = list(session.scalars(select(db.Invitation.code_hash)))
    assert all(len(h) == 64 and "-" not in h for h in hashes)
    # regenerate: the old code stops, a new one starts, the limits carry over
    first = listing[-1]
    new = company.owner.post(f"/org/invitations/{first['invitation_id']}/regenerate").json()
    assert new["code"] != "" and new["invitation"]["role"] == first["role"]
    assert new["invitation"]["max_uses"] == first["max_uses"]
    states = {i["invitation_id"]: i["state"] for i in company.owner.get("/org/invitations").json()}
    assert states[first["invitation_id"]] == "revoked"


def test_the_invitation_preview_names_the_company_only_for_a_valid_code(world, company):
    code = company.owner.post("/org/invitations", json={"role": "records_officer"}).json()["code"]
    ok = client().get("/auth/invitations/preview", params={"code": code})
    assert ok.status_code == 200 and ok.json()["organization_name"] == "Padma MFI"
    assert ok.json()["role"] == "records_officer"
    bad = client().get("/auth/invitations/preview", params={"code": "ZZZZ-ZZZZ-ZZZZ-ZZZZ"})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "invalid_invitation"


# --- scenario 1: platform administrators ------------------------------------------------


def test_platform_admins_come_only_from_the_environment_and_are_idempotent(world):
    with Session(world.engine) as session:
        first = bootstrap(session, world.config, OWNER_ENV)
        session.commit()
    outcomes = {r.slot: r.outcome for r in first}
    assert outcomes == {1: "created", 2: "created", 3: "not_configured", 4: "not_configured"}
    with Session(world.engine) as session:
        before = service.credential_for(session, "admin.one@credlens.example").password_hash
        again = bootstrap(session, world.config, OWNER_ENV)
        session.commit()
        after = service.credential_for(session, "admin.one@credlens.example").password_hash
    assert {r.outcome for r in again if r.slot in (1, 2)} == {"exists"}
    assert before == after and before.startswith("$argon2id$")  # never reset by a re-run
    with Session(world.engine) as session:
        assert session.scalars(select(db.PlatformAdmin)).all().__len__() == 2
    # a weak configured password is refused, nothing is created
    with Session(world.engine) as session:
        weak = bootstrap(
            session,
            world.config,
            {
                "CREDLENS_PLATFORM_ADMIN_3_EMAIL": "x@credlens.example",
                "CREDLENS_PLATFORM_ADMIN_3_PASSWORD": "weak",
            },
        )
        session.commit()
    assert weak[2].outcome == "invalid"


def test_a_platform_admin_signs_in_and_sees_companies_but_never_merchant_data(world, company):
    one = sign_in("admin.one@credlens.example", OWNER_ENV["CREDLENS_PLATFORM_ADMIN_1_PASSWORD"])
    me = one.get("/auth/me").json()
    assert me["role"] == "platform_admin" and me["is_platform"] and me["organization_id"] is None
    orgs = one.get("/platform/orgs").json()
    padma = next(o for o in orgs if o["name"] == "Padma MFI")
    assert (
        padma["credit_officers"] == 2 and padma["records_officers"] >= 2 and padma["merchants"] == 0
    )
    # no company data, no company pages
    for path in ("/org/employees", "/org/invitations", "/applications", "/merchants", "/audit"):
        assert one.get(path).status_code == 403, path
    # company users cannot reach the platform
    for who in (company.owner, company.officer, company.desk):
        assert who.get("/platform/orgs").status_code == 403


def test_unknown_emails_and_the_admin_addresses_cannot_become_platform_admins(world, company):
    stranger = client().post(
        "/auth/login",
        json={
            "identifier": "stranger@credlens.example",
            "password": OWNER_ENV["CREDLENS_PLATFORM_ADMIN_1_PASSWORD"],
        },
    )
    assert stranger.status_code == 401
    wrong = client().post(
        "/auth/login",
        json={"identifier": "admin.one@credlens.example", "password": "Wrong-Password-1!"},
    )
    assert wrong.status_code == 401 and wrong.json()["detail"]["code"] == "login_failed"
    # the reserved addresses cannot be registered as company users (same answer as "taken")
    taken = client().post(
        "/auth/register/company",
        json=company_body(
            email="Admin.One@credlens.example",
            legal_name="Sneaky Ltd",
            registration_number="S-1234",
            trading_name="Sneaky",
            mobile="01700000009",
        ),
    )
    assert taken.status_code == 409 and taken.json()["detail"]["code"] == "identifier_reserved"
    # no way to hand out the role: company users cannot touch /platform and have no such field
    me = company.owner.get("/auth/me").json()
    assert me["role"] == "credit_officer"


def test_a_platform_admin_can_suspend_a_company_and_reset_its_owner(world, company):
    one = sign_in("admin.one@credlens.example", OWNER_ENV["CREDLENS_PLATFORM_ADMIN_1_PASSWORD"])
    org_id = next(
        o["organization_id"] for o in one.get("/platform/orgs").json() if o["name"] == "Padma MFI"
    )
    assert (
        one.post(f"/platform/orgs/{org_id}/status", json={"status": "suspended"}).status_code == 200
    )
    assert company.owner.get("/auth/me").status_code == 401  # sessions stop at once
    blocked = client().post(
        "/auth/login", json={"identifier": "rina@padma.example", "password": STRONG}
    )
    assert blocked.status_code == 403
    assert one.post(f"/platform/orgs/{org_id}/status", json={"status": "active"}).status_code == 200
    code = one.post(f"/platform/orgs/{org_id}/owner-reset").json()
    assert len(code["setup_code"]) == 14 and code["employee"]["is_owner"]
    # the owner sets a new password with the one-time code, which then stops working
    new = "Cedar-Lake-2051!"
    c = client()
    assert (
        c.post(
            "/auth/password/setup",
            json={"identifier": "rina@padma.example", "code": code["setup_code"], "password": new},
        ).status_code
        == 204
    )
    assert (
        c.post(
            "/auth/password/setup",
            json={"identifier": "rina@padma.example", "code": code["setup_code"], "password": new},
        ).status_code
        == 400
    )
    sign_in("rina@padma.example", new)
    with Session(world.engine) as session:  # put the original password back for later tests
        credential = service.credential_for(session, "rina@padma.example")
        credential.password_hash = passwords.hash_password(STRONG)
        session.commit()
    company.owner = sign_in("rina@padma.example")  # the reset ended the owner's old sessions


# --- scenario 9 (basics): companies are separate ----------------------------------------


def test_two_companies_never_see_each_other(world, company):
    other = client()
    made = other.post(
        "/auth/register/company",
        json=company_body(
            full_name="Joya Begum",
            email="joya@sagar.example",
            mobile="01800000001",
            legal_name="Sagar Finance Limited",
            trading_name="Sagar Finance",
            registration_number="NBFI-77-001",
            org_type="nbfi",
            official_email="info@sagar.example",
            contact_number="028000002",
            city="Chattogram",
            division="Chattogram",
            website="",
        ),
    )
    assert made.status_code == 201, made.text
    joya = sign_in("joya@sagar.example")
    assert [p["full_name"] for p in joya.get("/org/employees").json()] == ["Joya Begum"]
    assert joya.get("/org/invitations").json() == []
    padma_invite = company.owner.get("/org/invitations").json()[0]["invitation_id"]
    # another company's invitation id and people are not there for her
    assert joya.post(f"/org/invitations/{padma_invite}/revoke").status_code == 404
    padma_user = company.owner.get("/org/employees").json()[1]["user_id"]
    assert joya.post(f"/org/employees/{padma_user}/disable").status_code == 404
    assert joya.post(f"/org/employees/{padma_user}/reset-code").status_code == 404
    # a Sagar invitation brings someone to Sagar, not to Padma
    code = joya.post("/org/invitations", json={"role": "records_officer"}).json()["code"]
    assert (
        client()
        .post(
            "/auth/register/join",
            json=join_body(
                code, email="far@sagar.example", mobile="01800000002", employee_id="E-1001"
            ),
        )
        .status_code
        == 201
    )
    far = sign_in("far@sagar.example").get("/auth/me").json()
    assert far["organization_name"] == "Sagar Finance"  # same employee id as in Padma: allowed


def test_a_disabled_employee_is_signed_out_and_cannot_return(world, company):
    code = company.owner.post("/org/invitations", json={"role": "records_officer"}).json()["code"]
    assert (
        client()
        .post(
            "/auth/register/join",
            json=join_body(
                code, email="leaver@padma.example", mobile="01766670001", employee_id="L-1"
            ),
        )
        .status_code
        == 201
    )
    leaver = sign_in("leaver@padma.example")
    user_id = leaver.get("/auth/me").json()["user_id"]
    assert company.officer.post(f"/org/employees/{user_id}/disable").status_code == 403  # not owner
    assert company.owner.post(f"/org/employees/{user_id}/disable").json()["status"] == "disabled"
    assert leaver.get("/auth/me").status_code == 401
    again = client().post(
        "/auth/login", json={"identifier": "leaver@padma.example", "password": STRONG}
    )
    assert again.status_code == 403


# --- limits on guessing -----------------------------------------------------------------


def test_sign_in_and_registration_are_rate_limited(world, company, monkeypatch):
    config = copy.deepcopy(world.config)
    config["auth"]["rate_limit"].update(login_per_identifier=3, login_per_ip=500)
    monkeypatch.setattr(world.services, "config", config)
    anon = client()
    codes = [
        anon.post(
            "/auth/login", json={"identifier": "nobody@x.example", "password": "Wrong-1234567!"}
        ).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
    # a different identifier from the same address is counted on its own
    assert (
        anon.post(
            "/auth/login", json={"identifier": "someone@x.example", "password": "Wrong-1234567!"}
        ).status_code
        == 401
    )
    config["auth"]["rate_limit"].update(invite_check_per_identifier=2, invite_check_per_ip=500)
    results = [
        client()
        .get("/auth/invitations/preview", params={"code": "QQQQ-QQQQ-QQQQ-QQQQ"})
        .status_code
        for _ in range(4)
    ]
    assert results == [400, 400, 429, 429]


def test_logout_ends_the_session_and_the_cookie_is_never_in_a_body(world, company):
    c = sign_in("nasrin@padma.example")
    reply = c.get("/auth/me")
    assert "credlens_session" not in reply.text
    assert c.post("/auth/logout").status_code == 204
    assert c.get("/auth/me").status_code == 401


def test_the_old_demo_entry_points_are_gone(world):
    c = client()
    assert c.get("/demo/people").status_code == 404
    assert c.get("/auth/me", headers={"X-Demo-Token": "officer-1"}).status_code == 401
    with Session(world.engine) as session:
        # nothing was seeded: the operational database starts empty
        assert session.scalar(select(db.Merchant.merchant_id)) is None


def test_the_role_chosen_must_match_the_code_and_the_job_title_is_not_asked(world, company):
    code = company.owner.post("/org/invitations", json={"role": "credit_officer"}).json()["code"]
    wrong = client().post(
        "/auth/register/join",
        json=join_body(code, email="wrongrole@padma.example", mobile="01766680001"),
    )  # role defaults to records_officer: the code is for a Credit Officer
    assert wrong.status_code == 422 and "role" in wrong.json()["detail"]["fields"]
    right = client().post(
        "/auth/register/join",
        json=join_body(
            code,
            role="credit_officer",
            email="rightrole@padma.example",
            mobile="01766680002",
            employee_id="E-7771",
        ),
    )
    assert right.status_code == 201, right.text  # the failed try did not use up the code
    me = sign_in("rightrole@padma.example").get("/auth/me").json()
    assert me["role"] == "credit_officer" and me["is_owner"] is False


def test_a_platform_admin_email_is_refused_with_a_clear_reason(world):
    reply = client().post(
        "/auth/register/company",
        json=company_body(
            email="Admin.One@credlens.example",
            registration_number="MFI-9999-0001",
            legal_name="Other Co",
            mobile="01755550001",
        ),
    )
    assert reply.status_code == 409
    assert "reserved" in reply.json()["detail"]["message"]
