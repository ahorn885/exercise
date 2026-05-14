-- populate_stimulus_components.sql
-- Targeted UPDATE for layer0.disciplines.stimulus_components
-- Operates only on canonical (non-superseded) rows.
-- Run AFTER confirming superseded_at IS NULL rows are the v1.3.1 canonical set.
-- Safe to re-run: UPDATEs are idempotent.

-- Enum (14 values, locked):
-- aerobic_low | aerobic_high | muscular_endurance_legs | muscular_endurance_upper |
-- pack_carry_load | vertical_gain | technical_descent | technical_handwork |
-- grip_strength | balance_dynamic | cold_exposure | fueling_practice |
-- cognitive_navigation | explosive_power

BEGIN;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','vertical_gain','technical_descent','balance_dynamic','fueling_practice']
WHERE discipline_id = 'D-001' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','fueling_practice']
WHERE discipline_id = 'D-002' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','muscular_endurance_legs','pack_carry_load','vertical_gain','balance_dynamic']
WHERE discipline_id = 'D-003' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_upper','technical_handwork','cold_exposure']
WHERE discipline_id = 'D-004' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_high','muscular_endurance_upper','technical_handwork']
WHERE discipline_id = 'D-004b' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','fueling_practice']
WHERE discipline_id = 'D-005' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_high','muscular_endurance_legs','fueling_practice']
WHERE discipline_id = 'D-005a' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','technical_descent','balance_dynamic','fueling_practice']
WHERE discipline_id = 'D-006' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','muscular_endurance_upper','technical_handwork','grip_strength','balance_dynamic','cold_exposure','fueling_practice']
WHERE discipline_id = 'D-007' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','muscular_endurance_upper','technical_handwork','grip_strength','fueling_practice']
WHERE discipline_id = 'D-008a' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_upper','technical_handwork','grip_strength','technical_descent','balance_dynamic','cold_exposure']
WHERE discipline_id = 'D-008b' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','muscular_endurance_upper','technical_handwork','grip_strength','fueling_practice']
WHERE discipline_id = 'D-009' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['muscular_endurance_upper','grip_strength','technical_handwork','balance_dynamic','vertical_gain']
WHERE discipline_id = 'D-010' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['technical_handwork','grip_strength','balance_dynamic']
WHERE discipline_id = 'D-011' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['muscular_endurance_upper','grip_strength','technical_handwork','balance_dynamic','vertical_gain']
WHERE discipline_id = 'D-012' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['cognitive_navigation','aerobic_low','aerobic_high','muscular_endurance_legs']
WHERE discipline_id = 'D-013' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','muscular_endurance_upper','technical_handwork','cold_exposure']
WHERE discipline_id = 'D-014' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','pack_carry_load','vertical_gain','balance_dynamic','cold_exposure']
WHERE discipline_id = 'D-015' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','pack_carry_load','vertical_gain','technical_handwork','grip_strength','balance_dynamic','cold_exposure','cognitive_navigation','fueling_practice']
WHERE discipline_id = 'D-016' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','muscular_endurance_upper','grip_strength','technical_handwork']
WHERE discipline_id = 'D-017' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','muscular_endurance_upper','technical_handwork','balance_dynamic','cold_exposure','fueling_practice']
WHERE discipline_id = 'D-018' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','vertical_gain','balance_dynamic','cold_exposure','fueling_practice']
WHERE discipline_id = 'D-019' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['technical_descent','balance_dynamic','muscular_endurance_legs','cold_exposure']
WHERE discipline_id = 'D-020' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['technical_handwork','balance_dynamic','vertical_gain','cold_exposure']
WHERE discipline_id = 'D-021' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','vertical_gain','pack_carry_load','cognitive_navigation','fueling_practice']
WHERE discipline_id = 'D-022' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['technical_descent','muscular_endurance_legs','balance_dynamic','aerobic_low']
WHERE discipline_id = 'D-023' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['explosive_power','balance_dynamic']
WHERE discipline_id = 'D-024' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_high','muscular_endurance_legs']
WHERE discipline_id = 'D-025' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['muscular_endurance_upper','muscular_endurance_legs','aerobic_high','grip_strength','balance_dynamic','explosive_power','vertical_gain']
WHERE discipline_id = 'D-026' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_low','aerobic_high','muscular_endurance_legs','muscular_endurance_upper','vertical_gain','balance_dynamic','cold_exposure','fueling_practice']
WHERE discipline_id = 'D-028' AND superseded_at IS NULL;

UPDATE layer0.disciplines SET stimulus_components = ARRAY['aerobic_high','muscular_endurance_legs','cold_exposure']
WHERE discipline_id = 'D-029' AND superseded_at IS NULL;

-- Verify: all 32 active disciplines now have stimulus_components populated
DO $$
DECLARE
  null_count INT;
BEGIN
  SELECT COUNT(*) INTO null_count
  FROM layer0.disciplines
  WHERE superseded_at IS NULL AND stimulus_components IS NULL;

  IF null_count > 0 THEN
    RAISE EXCEPTION 'populate_stimulus_components: % discipline rows still NULL after update', null_count;
  END IF;
  RAISE NOTICE 'populate_stimulus_components: all canonical rows populated OK';
END $$;

COMMIT;
