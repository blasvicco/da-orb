//! Renders a Crystal Reports `.rpt` template against a JSON data payload, entirely offline: no
//! live database, no report-embedded saved data. Orb's own process data (a session's
//! `form_state`/response JSON, mapped by the caller) is the only source of rows, parameters,
//! and subreport data.
//!
//! Usage: `orb-report-render <report.rpt> <data.json> <out.pdf>`
//!
//! `data.json` shape:
//! ```json
//! {
//!   "rows": [{"FieldName": value, ...}, ...],
//!   "params": {"ParamName": value, ...},
//!   "subreports": {"SubreportName.rpt": {"rows": [...]}, ...},
//!   "section_visibility": {"SectionName": true, ...},
//!   "object_visibility": {"ObjectName": true, ...}
//! }
//! ```
//! `rows` — one flat object per row, matching how Crystal itself models a report's data
//! (grouping/repeating sections are the report's own concern, layered on top of one flat row
//! source). Keys are matched against the report's own declared database-field names
//! (case-insensitively, by short name), so a template's own field schema is always the source
//! of truth for column names and types — the caller supplies values under the names the
//! template already declares. `params`, `subreports`, `section_visibility`, and
//! `object_visibility` are all optional; a template needing none of them needs none of these
//! keys.
//!
//! `params` — resolves a report's own `{?ParamName}` formula references (e.g. a
//! record-selection formula filtering by document key). Without this, a parameterized
//! template's selection formula fails to resolve and the pipeline's fail-open design silently
//! drops every row (`rpt-rs`'s `build_dataset_with_diagnostics` surfaces this as
//! `AllRowsExcluded` — reach for that when a render produces an unexpectedly empty document).
//!
//! `subreports` — feeds live rows into named subreports via `rpt-rs`'s `ScopeData` mechanism,
//! keyed by each subreport's own name (`Subreport.name`, e.g. `"TaxDetails.rpt"`) as declared
//! on the report.
//!
//! `section_visibility` — forces a named section (`Section.name`, e.g.
//! `"ReportHeaderSection3"`) visible (`true`) or hidden (`false`) regardless of what the .rpt
//! file's own static `suppress` flag or `Object_Visibility`/`Section_Visibility` formula would
//! otherwise decide, via `rpt-render`'s `RenderOptions::section_visibility`. Exists specifically
//! for sections some SAP B1 templates ship with a plain hard-coded suppress and no condition at
//! all (e.g. an alternate company-logo section, or one of several optional invoice-total lines)
//! — no amount of `rows`/`params` could ever influence those, so a customer-specific override
//! is the only way to turn one on. A name absent from the map defers entirely to the template's
//! own behavior; this is meant to be sparse, not a full inventory of every section.
//!
//! `object_visibility` — the same override, one level finer: forces a named *object*
//! (`ReportObject.name`, e.g. `"LogoImage2"`) visible or hidden, independent of its section's
//! own decision, via `RenderOptions::object_visibility`. This is the one that reaches inside a
//! section even when that section is a `Suppress` + "Underlay Following Sections" section — the
//! object override still applies, silencing just that object while the rest of the section's
//! content keeps underlaying. Needed when a section bundles more than one independently-relevant
//! object (e.g. a logo field sharing a section with unrelated company-letterhead fields, where
//! only the logo should be individually toggleable).

use rpt_data::{Column, Row, RowSource, ScopeData};
use rpt_formula::eval::{Date, Time, Value};
use rpt_model::{FieldDef, FieldKindData, FieldValueType, Report};
use rpt_render::{render_with, Parameters, RenderOptions, RenderSource};
use rpt_render_pdf::{try_render_document, PdfOptions};
use serde_json::Value as Json;
use std::collections::{BTreeMap, HashMap};

#[derive(Clone)]
struct JsonRows {
    columns: Vec<Column>,
    rows: Vec<Row>,
}

impl RowSource for JsonRows {
    fn columns(&self) -> &[Column] {
        &self.columns
    }

    fn rows(&self) -> Vec<Row> {
        self.rows.clone()
    }
}

fn field_key(field: &FieldDef) -> String {
    field
        .short_name
        .clone()
        .unwrap_or_else(|| field.name.clone())
        .to_lowercase()
}

fn parse_date(text: &str) -> Option<Date> {
    let date_part = text.split('T').next().unwrap_or(text);
    let mut parts = date_part.splitn(3, '-');
    let year = parts.next()?.parse().ok()?;
    let month = parts.next()?.parse().ok()?;
    let day = parts.next()?.parse().ok()?;
    Some(Date::new(year, month, day))
}

fn parse_time(text: &str) -> Option<Time> {
    let mut parts = text.splitn(3, ':');
    let hour = parts.next()?.parse().ok()?;
    let minute = parts.next()?.parse().ok()?;
    let second = parts.next().and_then(|value| value.parse().ok()).unwrap_or(0);
    Some(Time { hour, minute, second })
}

fn parse_datetime(text: &str) -> Option<(Date, Time)> {
    let mut parts = text.splitn(2, 'T');
    let date = parse_date(parts.next()?)?;
    let time = parts.next().and_then(parse_time).unwrap_or(Time { hour: 0, minute: 0, second: 0 });
    Some((date, time))
}

/// Coerce one JSON value into the `Value` its declared report field type expects. Missing,
/// null, or unparseable input becomes `Value::Null` rather than failing the whole render — a
/// blank field is how Crystal itself treats an unresolved value.
fn coerce(value_type: FieldValueType, json_value: Option<&Json>) -> Value {
    let json_value = match json_value {
        Some(value) if !value.is_null() => value,
        _ => return Value::Null,
    };
    match value_type {
        FieldValueType::Int8s
        | FieldValueType::Int16s
        | FieldValueType::Int32s
        | FieldValueType::Int32u
        | FieldValueType::Number => json_value.as_f64().map(Value::Number).unwrap_or(Value::Null),
        FieldValueType::Currency => json_value.as_f64().map(Value::Currency).unwrap_or(Value::Null),
        FieldValueType::Boolean => json_value.as_bool().map(Value::Bool).unwrap_or(Value::Null),
        FieldValueType::Date => json_value.as_str().and_then(parse_date).map(Value::Date).unwrap_or(Value::Null),
        FieldValueType::Time => json_value.as_str().and_then(parse_time).map(Value::Time).unwrap_or(Value::Null),
        FieldValueType::DateTime => json_value
            .as_str()
            .and_then(parse_datetime)
            .map(|(date, time)| Value::DateTime(date, time))
            .unwrap_or(Value::Null),
        _ => json_value.as_str().map(|text| Value::Str(text.to_string())).unwrap_or(Value::Null),
    }
}

fn build_row_source(report: &Report, payload: &Json) -> JsonRows {
    let database_fields: Vec<&FieldDef> = report
        .data_definition
        .field_definitions
        .iter()
        .filter(|field| matches!(field.kind, FieldKindData::Database(_)))
        .collect();

    let columns: Vec<Column> = database_fields
        .iter()
        .map(|field| Column {
            name: field.long_name.clone().unwrap_or_else(|| field.name.clone()),
            value_type: field.value_type,
        })
        .collect();

    let json_rows = payload.get("rows").and_then(Json::as_array).cloned().unwrap_or_default();
    let mut rows = Vec::new();
    for json_row in &json_rows {
        let mut lookup: HashMap<String, &Json> = HashMap::new();
        if let Some(object) = json_row.as_object() {
            for (key, value) in object {
                lookup.insert(key.to_lowercase(), value);
            }
        }
        let mut row = Row::default();
        for (field, column) in database_fields.iter().zip(&columns) {
            let value = coerce(column.value_type, lookup.get(&field_key(field)).copied());
            row.insert(&column.name, value);
        }
        rows.push(row);
    }

    JsonRows { columns, rows }
}

/// Parses `data.json`'s optional `params` object into report parameter values, resolving a
/// report's own `{?ParamName}` formula references. Keys are lowercased to match `rpt-rs`'s own
/// `normalize_param_name` convention; each value's JSON type picks its `Value` variant directly
/// (number/bool/string) since Crystal report parameters are simple scalars.
fn build_params(payload: &Json) -> Parameters {
    let mut params: Parameters = HashMap::new();
    if let Some(object) = payload.get("params").and_then(Json::as_object) {
        for (key, value) in object {
            let normalized = key.to_lowercase();
            let parsed = if let Some(number) = value.as_f64() {
                Value::Number(number)
            } else if let Some(boolean) = value.as_bool() {
                Value::Bool(boolean)
            } else if let Some(text) = value.as_str() {
                Value::Str(text.to_string())
            } else {
                Value::Null
            };
            params.insert(normalized, parsed);
        }
    }
    params
}

/// Parses `data.json`'s optional `section_visibility` object into rpt-rs's own override map
/// (`RenderOptions::section_visibility`), keyed by exact section name (e.g.
/// `"ReportHeaderSection3"`) with `true` meaning visible/not-suppressed and `false` meaning
/// force-hidden -- overriding whatever the .rpt file's own static `suppress` flag or
/// `Object_Visibility`/`Section_Visibility` formula would otherwise decide. Absent or `{}`
/// yields `None`, leaving every section's visibility exactly as the template author set it --
/// this key exists specifically for sections with no data-driven condition at all (a plain
/// hard-coded suppress), which no amount of `rows`/`params` could ever influence otherwise.
fn build_section_visibility(payload: &Json) -> Option<BTreeMap<String, bool>> {
    build_visibility_map(payload, "section_visibility")
}

/// Parses `data.json`'s optional `object_visibility` object the same way `section_visibility` is
/// parsed, into `RenderOptions::object_visibility`. See this file's module doc comment.
fn build_object_visibility(payload: &Json) -> Option<BTreeMap<String, bool>> {
    build_visibility_map(payload, "object_visibility")
}

fn build_visibility_map(payload: &Json, key: &str) -> Option<BTreeMap<String, bool>> {
    let object = payload.get(key).and_then(Json::as_object)?;
    if object.is_empty() {
        return None;
    }
    let mut overrides = BTreeMap::new();
    for (name, value) in object {
        if let Some(visible) = value.as_bool() {
            overrides.insert(name.clone(), visible);
        }
    }
    if overrides.is_empty() {
        None
    } else {
        Some(overrides)
    }
}

/// A structural fingerprint of a report, used to correlate a named subreport (known at
/// `SubreportScope::build` time, when the top-level report's own `subreports` list is walked)
/// against whatever `&Report` `ScopeData::rows_for` is later given. `rows_for` carries no name
/// of its own, and the render engine does not hand back the same `Report` instances a caller
/// sees via `Report::subreports` — pointer identity does not survive. This mirrors `rpt-rs`'s
/// own reference CLI (`apps/rpt-render-cli/src/datasource.rs`), which keys the same way for the
/// same reason: a report's record-selection formula text plus its database/table structure are
/// plain data, and do survive.
fn report_fingerprint(report: &Report) -> u64 {
    use std::hash::{Hash, Hasher};
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    format!("{:?}", report.data_definition.record_selection).hash(&mut hasher);
    format!("{:?}", report.database).hash(&mut hasher);
    hasher.finish()
}

/// Feeds `data.json`'s optional `subreports` object into named subreports via `ScopeData`. See
/// this file's module doc comment for the current linked-subreport layout limitation upstream.
struct SubreportScope {
    by_fingerprint: HashMap<u64, JsonRows>,
}

impl SubreportScope {
    fn build(report: &Report, payload: &Json) -> SubreportScope {
        let mut by_fingerprint = HashMap::new();
        if let Some(subreports_json) = payload.get("subreports").and_then(Json::as_object) {
            for subreport in &report.subreports {
                if let Some(sub_data) = subreports_json.get(&subreport.name) {
                    let key = report_fingerprint(&subreport.report);
                    by_fingerprint.insert(key, build_row_source(&subreport.report, sub_data));
                }
            }
        }
        SubreportScope { by_fingerprint }
    }
}

impl ScopeData for SubreportScope {
    fn rows_for(&self, report: &Report) -> Option<Box<dyn RowSource>> {
        let key = report_fingerprint(report);
        self.by_fingerprint.get(&key).map(|source| Box::new(source.clone()) as Box<dyn RowSource>)
    }
}

fn main() {
    let mut args = std::env::args().skip(1);
    let usage = "usage: orb-report-render <report.rpt> <data.json> <out.pdf>";
    let report_path = args.next().expect(usage);
    let data_path = args.next().expect(usage);
    let output_path = args.next().expect(usage);

    let rpt = rpt_reader::Rpt::open(&report_path).expect("open report");
    let report = rpt.report();

    let data_text = std::fs::read_to_string(&data_path).expect("read data json");
    let payload: Json = serde_json::from_str(&data_text).expect("parse data json");
    let source = build_row_source(report, &payload);
    let params = build_params(&payload);
    let scope = SubreportScope::build(report, &payload);
    let section_visibility = build_section_visibility(&payload);
    let object_visibility = build_object_visibility(&payload);

    let doc = render_with(
        report,
        RenderOptions {
            datasource: RenderSource::Rows(&source),
            params,
            scope: Some(&scope),
            section_visibility,
            object_visibility,
            ..Default::default()
        },
    );

    let pdf = try_render_document(&doc, &PdfOptions::default()).expect("render pdf");
    std::fs::write(&output_path, pdf).expect("write pdf");
}
