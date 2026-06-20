"""Provider outbound serializer tests (#681 Wave 3b).

Pure-function coverage of `routes.outbound_workout` (session→steps, Zwift `.zwo`,
TrainingPeaks `Structure`) plus the Zwift `.zwo` download route. Mappings per
`specs/Provider_Inbound_Matrix_v2.md` §11; design
`designs/ProviderOutbound_StructuredWorkout_681_Wave3b_BuildDesign_v1.md`.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from flask import Flask

from routes import outbound_workout as ow


def _block(kind, dur, zone, instr='', **kw):
    b = {'block_kind': kind, 'duration_min': dur, 'intensity_zone': zone,
         'instructions': instr}
    b.update(kw)
    return b


def _bike_session():
    return {
        'session_id': 's1', 'kind': 'cardio', 'date': '2026-06-20',
        'discipline_id': 'D-006', 'discipline_name': 'Road Cycling',
        'cardio_blocks': [
            _block('warmup', 10, 'Z1', 'easy spin'),
            _block('main_set', 20, 'Z3', 'tempo'),
            _block('interval_set', 4, 'Z5', '5x4min', repetitions=5,
                   rest_between_min=2, rest_intensity_zone='Z1'),
            _block('cooldown', 5, 'Z1', 'spin down'),
        ],
    }


def _run_session():
    s = _bike_session()
    s['discipline_id'] = 'D-002'
    s['discipline_name'] = 'Road Running'
    return s


# ── session_to_steps ──────────────────────────────────────────────────

class TestSessionToSteps:
    def test_flattens_blocks(self):
        steps = ow.session_to_steps(_bike_session())
        assert [s.kind for s in steps] == [
            'warmup', 'main_set', 'interval_set', 'cooldown']
        assert steps[0].duration_s == 600  # 10 min → s

    def test_interval_carries_rep_and_rest(self):
        iv = ow.session_to_steps(_bike_session())[2]
        assert iv.reps == 5
        assert iv.duration_s == 240
        assert iv.rest_duration_s == 120
        assert iv.rest_zone == 'Z1'

    def test_mixed_zone_collapses_to_z2(self):
        s = _bike_session()
        s['cardio_blocks'] = [_block('main_set', 30, 'mixed')]
        assert ow.session_to_steps(s)[0].zone == 'Z2'

    def test_non_cardio_raises(self):
        for kind in ('strength', 'rest', 'recovery'):
            try:
                ow.session_to_steps({'kind': kind})
                assert False, f'{kind} should raise'
            except ValueError:
                pass

    def test_empty_blocks_raises(self):
        try:
            ow.session_to_steps({'kind': 'cardio', 'cardio_blocks': []})
            assert False
        except ValueError:
            pass


# ── Zwift .zwo ─────────────────────────────────────────────────────────

class TestZwo:
    def _root(self, session):
        return ET.fromstring(ow.to_zwo(session))

    def test_bike_sport_type(self):
        root = self._root(_bike_session())
        assert root.find('sportType').text == 'bike'

    def test_run_sport_type(self):
        root = self._root(_run_session())
        assert root.find('sportType').text == 'run'

    def test_warmup_is_ramp_band(self):
        wu = self._root(_bike_session()).find('workout/Warmup')
        assert wu.get('Duration') == '600'
        # Z1 band low/high (0.50/0.55)
        assert wu.get('PowerLow') == '0.500'
        assert wu.get('PowerHigh') == '0.550'

    def test_cooldown_ramps_down(self):
        cd = self._root(_bike_session()).find('workout/Cooldown')
        # ramp DOWN → high first
        assert float(cd.get('PowerLow')) > float(cd.get('PowerHigh'))

    def test_steady_state_midpoint(self):
        ss = self._root(_bike_session()).find('workout/SteadyState')
        # Z3 midpoint of (0.76, 0.90) = 0.83
        assert ss.get('Power') == '0.830'

    def test_intervals_block(self):
        iv = self._root(_bike_session()).find('workout/IntervalsT')
        assert iv.get('Repeat') == '5'
        assert iv.get('OnDuration') == '240'
        assert iv.get('OffDuration') == '120'
        # Z5 on (mid 1.13), Z1 off (mid 0.525)
        assert iv.get('OnPower') == '1.130'

    def test_non_bike_run_discipline_raises(self):
        s = _bike_session()
        s['discipline_id'] = 'D-003'  # hiking → not Zwift-exportable
        try:
            ow.to_zwo(s)
            assert False
        except ValueError:
            pass

    def test_well_formed_xml(self):
        # parses without error → well-formed
        ET.fromstring(ow.to_zwo(_run_session()))


# ── TrainingPeaks Structure ────────────────────────────────────────────

class TestTpStructure:
    def test_cycling_uses_percent_of_ftp(self):
        out = ow.to_tp_structure(_bike_session())
        assert out['IntensityTargetType'] == 'PercentOfFtp'
        first = out['Structure'][0]['Steps'][0]
        assert first['IntensityTarget']['Unit'] == 'PercentOfFtp'
        assert first['Length']['Unit'] == 'Second'

    def test_running_uses_threshold_hr(self):
        out = ow.to_tp_structure(_run_session())
        assert out['IntensityTargetType'] == 'PercentOfThresholdHr'

    def test_interval_is_repetition(self):
        out = ow.to_tp_structure(_bike_session())
        rep = out['Structure'][2]  # interval_set
        assert rep['Type'] == 'Repetition'
        assert rep['Length'] == {'Value': 5, 'Unit': 'Repetition'}
        assert len(rep['Steps']) == 2  # work + rest

    def test_single_step_wrapped_as_repetition_of_one(self):
        out = ow.to_tp_structure(_bike_session())
        wu = out['Structure'][0]
        assert wu['Length'] == {'Value': 1, 'Unit': 'Repetition'}
        assert wu['Steps'][0]['IntensityClass'] == 'WarmUp'


# ── Zwift .zwo download route ──────────────────────────────────────────

class TestZwiftExportRoute:
    def _client(self, monkeypatch, session, uid=7):
        from routes.zwift import bp
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app = Flask(__name__, template_folder=os.path.join(root, 'templates'))
        app.config['TESTING'] = True
        app.register_blueprint(bp)
        import routes.zwift as zmod
        monkeypatch.setattr(zmod, 'current_user_id', lambda: uid)
        monkeypatch.setattr(zmod, 'get_db', lambda: object())
        monkeypatch.setattr(zmod, 'load_plan_session_payload',
                            lambda *a, **k: session)
        return app.test_client()

    def test_cardio_session_downloads_zwo(self, monkeypatch):
        c = self._client(monkeypatch, _bike_session())
        r = c.get('/zwift/export/12/2026-06-20/0.zwo')
        assert r.status_code == 200
        assert r.mimetype == 'application/octet-stream'
        assert 'attachment' in r.headers['Content-Disposition']
        assert b'<workout_file>' in r.data

    def test_missing_session_404(self, monkeypatch):
        c = self._client(monkeypatch, None)
        assert c.get('/zwift/export/12/2026-06-20/0.zwo').status_code == 404

    def test_non_cardio_session_400(self, monkeypatch):
        c = self._client(monkeypatch, {'kind': 'strength', 'session_id': 'x'})
        assert c.get('/zwift/export/12/2026-06-20/0.zwo').status_code == 400

    def test_non_exportable_discipline_400(self, monkeypatch):
        s = _bike_session()
        s['discipline_id'] = 'D-003'  # hiking
        c = self._client(monkeypatch, s)
        assert c.get('/zwift/export/12/2026-06-20/0.zwo').status_code == 400
