-- When a note is linked to a company (or to a person of a company), set company."lastContactAt" to today.
-- Never moves the date backwards. Idempotent. Run with: psql -v schema=<workspace schema> -f this-file
-- Requires the custom company field "lastContactAt" (DATE).
SET search_path TO :"schema";

CREATE OR REPLACE FUNCTION bump_last_contact() RETURNS trigger AS $$
DECLARE cid uuid := NEW."targetCompanyId";
BEGIN
  IF cid IS NULL AND NEW."targetPersonId" IS NOT NULL THEN
    SELECT "companyId" INTO cid FROM person WHERE id = NEW."targetPersonId";
  END IF;
  IF cid IS NOT NULL THEN
    UPDATE company SET "lastContactAt" = CURRENT_DATE
    WHERE id = cid AND ("lastContactAt" IS NULL OR "lastContactAt" < CURRENT_DATE);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql SET search_path FROM CURRENT;  -- Twenty's connection uses another search_path

DROP TRIGGER IF EXISTS note_target_bump_last_contact ON "noteTarget";
CREATE TRIGGER note_target_bump_last_contact AFTER INSERT ON "noteTarget"
  FOR EACH ROW EXECUTE FUNCTION bump_last_contact();
