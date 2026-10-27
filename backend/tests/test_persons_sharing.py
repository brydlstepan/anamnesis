def test_own_person_and_update(make_user):
    alice = make_user("alice@example.com")
    persons = alice.get("/api/v1/persons").json()
    assert len(persons) == 1 and persons[0]["role"] == "owner" and persons[0]["is_me"]
    pid = persons[0]["id"]
    r = alice.patch(f"/api/v1/persons/{pid}", json={"name": "Alice A.", "body_model": "female", "blood_type": "A+",
                                                     "birth_date": "1990-04-02"})
    assert r.status_code == 200, r.text
    assert r.json()["body_model"] == "female"
    assert alice.patch(f"/api/v1/persons/{pid}", json={"blood_type": "Z"}).status_code == 422
    assert alice.patch(f"/api/v1/persons/{pid}", json={"body_model": "robot"}).status_code == 422


def test_sharing_roles(make_user):
    alice = make_user("alice@example.com")
    bob = make_user("bob@example.com")
    carol = make_user("carol@example.com")
    apid = alice.me["person_id"]

    # no access -> 404 (no enumeration)
    assert bob.get(f"/api/v1/persons/{apid}").status_code == 404

    # viewer
    r = alice.post(f"/api/v1/persons/{apid}/shares", json={"email": "Bob@Example.com", "role": "viewer"})
    assert r.status_code == 201 and r.json()["status"] == "active"
    share_id = r.json()["id"]
    assert bob.get(f"/api/v1/persons/{apid}").json()["role"] == "viewer"
    rec = {"type": "condition", "title": "Asthma", "date": "2012", "status": "active"}
    assert bob.post(f"/api/v1/persons/{apid}/records", json=rec).status_code == 403
    assert bob.patch(f"/api/v1/persons/{apid}", json={"name": "x"}).status_code == 403

    # upgrade to editor
    assert alice.patch(f"/api/v1/shares/{share_id}", json={"role": "editor"}).status_code == 200
    assert bob.post(f"/api/v1/persons/{apid}/records", json=rec).status_code == 201
    # editors cannot re-share or see shares / access log
    assert bob.post(f"/api/v1/persons/{apid}/shares", json={"email": "carol@example.com", "role": "viewer"}).status_code == 403
    assert bob.get(f"/api/v1/persons/{apid}/shares").status_code == 403
    assert bob.get(f"/api/v1/persons/{apid}/access-log").status_code == 403
    # bob sees alice in his list
    roles = {p["name"]: p["role"] for p in bob.get("/api/v1/persons").json()}
    assert roles["alice@example.com"] == "editor"
    # carol cannot touch alice's share
    assert carol.delete(f"/api/v1/shares/{share_id}").status_code == 404

    # revoke
    assert alice.delete(f"/api/v1/shares/{share_id}").status_code == 204
    assert bob.get(f"/api/v1/persons/{apid}").status_code == 404

    # owner sees access log incl. bob's view
    log = alice.get(f"/api/v1/persons/{apid}/access-log").json()
    actions = {(e["actor"], e["action"]) for e in log}
    assert ("bob@example.com", "person.view") in actions
    assert ("bob@example.com", "record.create") in actions


def test_pending_share_activates_on_user_creation(make_user):
    alice = make_user("alice@example.com")
    apid = alice.me["person_id"]
    r = alice.post(f"/api/v1/persons/{apid}/shares", json={"email": "dave@example.com", "role": "viewer"})
    assert r.json()["status"] == "pending"
    assert alice.post(f"/api/v1/persons/{apid}/shares", json={"email": "dave@example.com", "role": "editor"}).status_code == 409
    assert alice.post(f"/api/v1/persons/{apid}/shares", json={"email": "alice@example.com", "role": "viewer"}).status_code == 422
    dave = make_user("dave@example.com")
    assert any(p["id"] == apid for p in dave.get("/api/v1/persons").json())
    assert alice.get(f"/api/v1/persons/{apid}/shares").json()[0]["status"] == "active"
