"""Tests for the TCX/GPX activity parser + bulk dispatch (#767 slice 2).

`parse_tcx` / `parse_gpx` emit the same normalized cardio dict `parse_fit`
produces, so the shared `_bulk_insert_cardio` writer ingests them unchanged.
These cover the per-format parse (metrics, unit conversion, discipline
resolution, record-don't-drop) and the `routes.garmin` blob dispatch that routes
.fit/.tcx/.gpx (incl. inside zips) to the right parser.

Fixtures below are hand-authored but schema-faithful to the documented public
standards (Garmin TCX v2, Topografix GPX 1.1 + the Garmin TrackPointExtension) —
license-clean and deterministic, unlike fetched third-party sample files.
"""

import io
import zipfile

import pytest

from tcx_gpx_parser import parse_tcx, parse_gpx, detect_source
import routes.garmin as g
from routes.garmin import _blob_ext, _iter_activity_blobs


# ─── fixtures ────────────────────────────────────────────────────────────────

TCX_RUN = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
    xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
  <Activities>
    <Activity Sport="Running">
      <Id>2026-06-15T13:00:00Z</Id>
      <Lap StartTime="2026-06-15T13:00:00Z">
        <TotalTimeSeconds>600</TotalTimeSeconds>
        <DistanceMeters>1609.34</DistanceMeters>
        <Calories>120</Calories>
        <AverageHeartRateBpm><Value>150</Value></AverageHeartRateBpm>
        <Track>
          <Trackpoint>
            <Time>2026-06-15T13:00:00Z</Time>
            <AltitudeMeters>100</AltitudeMeters>
            <DistanceMeters>0</DistanceMeters>
            <HeartRateBpm><Value>140</Value></HeartRateBpm>
            <Cadence>85</Cadence>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-06-15T13:05:00Z</Time>
            <AltitudeMeters>110</AltitudeMeters>
            <DistanceMeters>800</DistanceMeters>
            <HeartRateBpm><Value>160</Value></HeartRateBpm>
            <Cadence>88</Cadence>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-06-15T13:10:00Z</Time>
            <AltitudeMeters>105</AltitudeMeters>
            <DistanceMeters>1609.34</DistanceMeters>
            <HeartRateBpm><Value>150</Value></HeartRateBpm>
            <Cadence>86</Cadence>
          </Trackpoint>
        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>"""

TCX_BIKE = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
    xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
  <Activities>
    <Activity Sport="Biking">
      <Id>2026-06-15T08:00:00Z</Id>
      <Lap StartTime="2026-06-15T08:00:00Z">
        <TotalTimeSeconds>1800</TotalTimeSeconds>
        <DistanceMeters>16093.4</DistanceMeters>
        <Track>
          <Trackpoint>
            <Time>2026-06-15T08:00:00Z</Time>
            <DistanceMeters>0</DistanceMeters>
            <Extensions><ns3:TPX><ns3:Watts>180</ns3:Watts></ns3:TPX></Extensions>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-06-15T08:30:00Z</Time>
            <DistanceMeters>16093.4</DistanceMeters>
            <Extensions><ns3:TPX><ns3:Watts>220</ns3:Watts></ns3:TPX></Extensions>
          </Trackpoint>
        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>"""

TCX_OTHER = TCX_RUN.replace(b'Sport="Running"', b'Sport="Other"')

GPX_RUN = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <trk>
    <name>Morning Run</name>
    <type>running</type>
    <trkseg>
      <trkpt lat="44.9000" lon="-93.0000">
        <ele>250</ele><time>2026-06-16T12:00:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>142</gpxtpx:hr><gpxtpx:cad>80</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
      <trkpt lat="44.9050" lon="-93.0000">
        <ele>260</ele><time>2026-06-16T12:03:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>158</gpxtpx:hr><gpxtpx:cad>82</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
      <trkpt lat="44.9100" lon="-93.0000">
        <ele>255</ele><time>2026-06-16T12:06:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>150</gpxtpx:hr><gpxtpx:cad>81</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
    </trkseg>
  </trk>
</gpx>"""

GPX_NOTYPE = GPX_RUN.replace(b'<type>running</type>', b'')


# ─── TCX ─────────────────────────────────────────────────────────────────────

class TestParseTcx:
    def test_running_shape_and_metrics(self):
        out = parse_tcx(TCX_RUN)
        assert out['log_type'] == 'cardio'
        d = out['data']
        assert d['date'] == '2026-06-15'
        assert d['activity'] == 'Running'
        assert d['discipline_id'] == 'D-002'
        assert d['duration_min'] == 10.0
        assert d['moving_time_min'] == 10.0
        assert d['distance_mi'] == pytest.approx(1.0, abs=0.01)
        assert d['avg_hr'] == 150
        assert d['max_hr'] == 160
        assert d['calories'] == 120
        # one-leg cadence doubled to full strides for foot sports
        assert d['avg_cadence'] == 172   # round(86.33) * 2
        assert d['max_cadence'] == 176   # 88 * 2
        assert d['avg_pace'] == '10:00'
        assert d['elev_gain_ft'] == pytest.approx(32.8, abs=0.2)
        assert d['elev_loss_ft'] == pytest.approx(16.4, abs=0.2)
        # running dynamics absent in TCX
        assert d['stride_length_m'] is None and d['norm_power'] is None

    def test_provider_raw_records_format_and_bucket(self):
        raw = parse_tcx(TCX_RUN)['data']['_provider_raw']
        assert raw['provider'] == 'manual'      # overridden by upload source later
        assert raw['bucket'] == 1
        assert raw['canonical_ref'] == 'D-002'
        assert raw['payload']['format'] == 'tcx'
        assert raw['payload']['sport'] == 'Running'

    def test_biking_resolves_cycling_and_power(self):
        d = parse_tcx(TCX_BIKE)['data']
        assert d['activity'] == 'Cycling'
        assert d['discipline_id'] == 'D-006'
        assert d['avg_power'] == 200   # (180 + 220) / 2
        assert d['max_power'] == 220
        assert d['avg_cadence'] is None      # no cadence in this file
        assert d['avg_pace'] is None         # not a foot sport

    def test_unmapped_sport_is_bucket3_no_discipline(self):
        d = parse_tcx(TCX_OTHER)['data']
        assert d['activity'] == 'Activity'
        assert d['discipline_id'] is None
        assert d['_provider_raw']['bucket'] == 3

    def test_malformed_xml_raises_valueerror(self):
        with pytest.raises(ValueError):
            parse_tcx(b'<TrainingCenterDatabase><not closed')

    def test_no_activity_raises_valueerror(self):
        with pytest.raises(ValueError):
            parse_tcx(b'<?xml version="1.0"?><TrainingCenterDatabase/>')


# ─── GPX ─────────────────────────────────────────────────────────────────────

class TestParseGpx:
    def test_running_geometry_distance_and_streams(self):
        d = parse_gpx(GPX_RUN)['data']
        assert d['date'] == '2026-06-16'
        assert d['activity'] == 'Running'
        assert d['discipline_id'] == 'D-002'
        assert d['duration_min'] == 6.0
        assert d['moving_time_min'] is None    # GPX has no lap timer
        # ~0.01 deg of latitude ≈ 1.1 km ≈ 0.69 mi (haversine-integrated)
        assert d['distance_mi'] == pytest.approx(0.69, abs=0.05)
        assert d['avg_hr'] == 150
        assert d['max_hr'] == 158
        assert d['avg_cadence'] == 162    # round(81) * 2 (foot sport)
        assert d['elev_gain_ft'] == pytest.approx(32.8, abs=0.2)
        assert d['elev_loss_ft'] == pytest.approx(16.4, abs=0.2)

    def test_no_type_is_bucket3(self):
        d = parse_gpx(GPX_NOTYPE)['data']
        assert d['discipline_id'] is None
        assert d['activity'] == 'Activity'
        assert d['_provider_raw']['bucket'] == 3
        assert d['_provider_raw']['payload']['format'] == 'gpx'

    def test_no_trackpoints_raises_valueerror(self):
        with pytest.raises(ValueError):
            parse_gpx(b'<?xml version="1.0"?>'
                      b'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk/></gpx>')

    def test_no_track_raises_valueerror(self):
        with pytest.raises(ValueError):
            parse_gpx(b'<?xml version="1.0"?>'
                      b'<gpx xmlns="http://www.topografix.com/GPX/1/1"/>')


# ─── source auto-detection (#1055) ───────────────────────────────────────────

class TestDetectSource:
    def test_tcx_author_name_detected(self):
        tcx = TCX_RUN.replace(
            b'</Activities>',
            b'</Activities><Author><Name>COROS App</Name></Author>')
        assert detect_source(tcx, 'tcx') == 'coros'

    def test_tcx_polar_flow_detected(self):
        tcx = TCX_RUN.replace(
            b'</Activities>',
            b'</Activities><Author><Name>Polar Flow</Name></Author>')
        assert detect_source(tcx, 'tcx') == 'polar'

    def test_gpx_creator_attribute_detected(self):
        gpx = GPX_RUN.replace(b'creator="test"', b'creator="StravaGPX"')
        assert detect_source(gpx, 'gpx') == 'strava'

    def test_gpx_wahoo_creator_detected(self):
        gpx = GPX_RUN.replace(b'creator="test"', b'creator="Wahoo Fitness"')
        assert detect_source(gpx, 'gpx') == 'wahoo'

    def test_unrecognized_creator_falls_back_to_garmin(self):
        assert detect_source(GPX_RUN, 'gpx') == 'garmin'  # creator="test"

    def test_no_author_falls_back_to_garmin(self):
        assert detect_source(TCX_RUN, 'tcx') == 'garmin'

    def test_malformed_xml_falls_back_to_garmin(self):
        assert detect_source(b'<not closed', 'tcx') == 'garmin'


# ─── blob dispatch (routes.garmin) ───────────────────────────────────────────

class _Upload:
    """Minimal werkzeug FileStorage stand-in: filename + read()."""

    def __init__(self, filename, data):
        self.filename = filename
        self._data = data

    def read(self):
        return self._data


class TestBlobExt:
    def test_recognizes_activity_extensions(self):
        assert _blob_ext('ride.fit') == 'fit'
        assert _blob_ext('run.TCX') == 'tcx'
        assert _blob_ext('hike.gpx') == 'gpx'

    def test_recognizes_wellness_csv(self):
        # #767 slice 5 — a WHOOP physiological_cycles.csv is now ingestible
        # (routed to the wellness path, not cardio_log).
        assert _blob_ext('physiological_cycles.csv') == 'csv'
        assert _blob_ext('CYCLES.CSV') == 'csv'

    def test_rejects_non_ingestible(self):
        assert _blob_ext('export.zip') is None
        assert _blob_ext('readme.txt') is None


class TestIterActivityBlobs:
    def test_plain_files_carry_ext(self):
        out = list(_iter_activity_blobs([
            _Upload('a.tcx', TCX_RUN),
            _Upload('b.gpx', GPX_RUN),
        ]))
        assert [(n.split('.')[-1], ext, err) for n, _r, ext, err in out] == [
            ('tcx', 'tcx', None), ('gpx', 'gpx', None)]

    def test_csv_blob_carries_csv_ext(self):
        # #767 slice 5 — a .csv yields ext='csv' (the import_bulk loop routes it
        # to the WHOOP wellness path); the parser validates the contents later.
        (name, raw, ext, err), = _iter_activity_blobs([_Upload('cycles.csv', b'a,b')])
        assert ext == 'csv' and err is None and raw == b'a,b'

    def test_unsupported_file_is_an_error(self):
        (name, raw, ext, err), = _iter_activity_blobs([_Upload('notes.txt', b'hi')])
        assert raw is None and ext is None and 'not a' in err

    def test_zip_expands_to_entries_with_ext(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('folder/run.gpx', GPX_RUN)
            zf.writestr('folder/notes.txt', b'ignore me')
        out = list(_iter_activity_blobs([_Upload('export.zip', buf.getvalue())]))
        assert len(out) == 1
        name, raw, ext, err = out[0]
        assert ext == 'gpx' and err is None and raw == GPX_RUN

    def test_zip_without_activities_reports_error(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('readme.txt', b'nothing here')
        (name, raw, ext, err), = _iter_activity_blobs([_Upload('export.zip', buf.getvalue())])
        assert raw is None and 'no .fit/.tcx/.gpx/.csv' in err
