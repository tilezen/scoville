CREATE TABLE scoville_measurements (
  id          BIGINT                                  NOT NULL,
  "timestamp" TIMESTAMP   ENCODE delta                NOT NULL,
  region      VARCHAR(20) ENCODE bytedict             NOT NULL,
  source      VARCHAR(20) ENCODE bytedict             NOT NULL,
  coord_z     SMALLINT    ENCODE delta                NOT NULL,
  coord_x     INTEGER     ENCODE mostly16             NOT NULL,
  coord_y     INTEGER     ENCODE mostly16             NOT NULL,
  status_code SMALLINT    ENCODE bytedict             NOT NULL,
  PRIMARY KEY(id))
  DISTSTYLE KEY DISTKEY(id)
  INTERLEAVED SORTKEY("timestamp", region, source, coord_z, coord_x, coord_y);

CREATE TABLE scoville_tile_info (
  measurement_id        BIGINT      ENCODE delta NOT NULL,
  bytes_received        INTEGER     ENCODE mostly16 NOT NULL,
  bytes_uncompressed    INTEGER     ENCODE mostly16 NOT NULL,
  content_encoding      VARCHAR(40) ENCODE bytedict NOT NULL,
  content_type          VARCHAR(40) ENCODE bytedict,
  namelookup_time_ms    INTEGER     ENCODE mostly16 NOT NULL,
  connect_time_ms       INTEGER     ENCODE mostly16 NOT NULL,
  appconnect_time_ms    INTEGER     ENCODE mostly16 NOT NULL,
  pretransfer_time_ms   INTEGER     ENCODE mostly16 NOT NULL,
  starttransfer_time_ms INTEGER     ENCODE mostly16 NOT NULL,
  total_time_ms         INTEGER     ENCODE mostly16 NOT NULL,
  server_source         VARCHAR(20) ENCODE bytedict,
  FOREIGN KEY(measurement_id) REFERENCES scoville_measurements(id))
  DISTSTYLE KEY DISTKEY(measurement_id);

CREATE TABLE scoville_layer_info (
  measurement_id   BIGINT      ENCODE delta NOT NULL,
  name             VARCHAR(20) ENCODE bytedict NOT NULL,
  bytes            INTEGER     ENCODE mostly16 NOT NULL,
  num_points       INTEGER     ENCODE mostly8 NOT NULL,
  num_lines        INTEGER     ENCODE mostly8 NOT NULL,
  num_polygons     INTEGER     ENCODE mostly8 NOT NULL,
  num_empty        INTEGER     ENCODE mostly8 NOT NULL,
  line_coords      INTEGER     ENCODE mostly16 NOT NULL,
  polygon_coords   INTEGER     ENCODE mostly16 NOT NULL,
  line_length_cpx  INTEGER     ENCODE mostly16 NOT NULL,
  polygon_area_cpx INTEGER     ENCODE mostly16 NOT NULL,
  features         INTEGER     ENCODE mostly16 NOT NULL,
  num_props        INTEGER     ENCODE mostly16 NOT NULL,
  prop_bytes       INTEGER     ENCODE mostly16 NOT NULL,
  uniq_num_props   INTEGER     ENCODE mostly16 NOT NULL,
  uniq_prop_bytes  INTEGER     ENCODE mostly16 NOT NULL,
  FOREIGN KEY(measurement_id) REFERENCES scoville_measurements(id))
  DISTSTYLE KEY DISTKEY(measurement_id);

CREATE TABLE scoville_layer_kind_info (
  measurement_id   BIGINT      ENCODE delta NOT NULL,
  name             VARCHAR(20) ENCODE bytedict NOT NULL,
  kind             VARCHAR(20) ENCODE bytedict NOT NULL,
  "count"          INTEGER     ENCODE mostly8 NOT NULL,
  FOREIGN KEY(measurement_id) REFERENCES scoville_measurements(id))
  DISTSTYLE KEY DISTKEY(measurement_id);
