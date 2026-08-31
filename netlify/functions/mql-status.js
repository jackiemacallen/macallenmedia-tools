const AIRTABLE_TOKEN   = process.env.AIRTABLE_TOKEN;
const AIRTABLE_BASE_ID = process.env.AIRTABLE_BASE_ID;
const TABLE_NAME       = "MQL Status Tracker";

const corsHeaders = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

async function airtableFetch(path, options = {}) {
  const url = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${encodeURIComponent(TABLE_NAME)}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Authorization": `Bearer ${AIRTABLE_TOKEN}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  let data;
  try {
    data = await res.json();
  } catch (parseErr) {
    data = null;
  }

  // Airtable returns a non-2xx status with an {error:{...}} body when a write
  // fails (e.g. a Status value that no longer matches a valid select option).
  // Surfacing that here is what fixes the historical "silent failure" bug --
  // previously this function returned whatever Airtable sent back without
  // checking it, so a rejected write still looked like {"success":true}.
  if (!res.ok) {
    const msg = (data && data.error && (data.error.message || data.error.type))
      || `Airtable request failed with status ${res.status}`;
    throw new Error(msg);
  }

  return data;
}

exports.handler = async function(event) {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 200, headers: corsHeaders, body: "" };
  }

  try {
    if (event.httpMethod === "GET") {
      const dashboard = (event.queryStringParameters || {}).dashboard || "";
      const formula   = dashboard
        ? `AND({Dashboard}="${dashboard}", {Status}!="cleared")`
        : `{Status}!="cleared"`;

      const data = await airtableFetch(
        `?filterByFormula=${encodeURIComponent(formula)}&fields[]=Email&fields[]=Status&fields[]=Dashboard&fields[]=Period&fields[]=Updated+At`
      );

      const rows = (data.records || []).map(r => ({
        email:      r.fields["Email"]      || "",
        status:     r.fields["Status"]     || "",
        dashboard:  r.fields["Dashboard"]  || "",
        period:     r.fields["Period"]     || "",
        updated_at: r.fields["Updated At"] || "",
      }));

      return {
        statusCode: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ rows }),
      };
    }

    if (event.httpMethod === "POST") {
      const { email, status, dashboard, period, updated_at } = JSON.parse(event.body);

      if (!email) {
        return { statusCode: 400, headers: corsHeaders, body: JSON.stringify({ success: false, error: "Missing email" }) };
      }

      const updatedAt = updated_at || new Date().toISOString();

      const existing = await airtableFetch(
        `?filterByFormula=${encodeURIComponent(`AND({Email}="${email}", {Dashboard}="${dashboard}")`)}` +
        `&fields[]=Email&fields[]=Dashboard`
      );

      if (existing.records && existing.records.length > 0) {
        const recordId = existing.records[0].id;
        await airtableFetch(`/${recordId}`, {
          method: "PATCH",
          body: JSON.stringify({
            fields: {
              "Status":     status,
              "Period":     period,
              "Updated At": updatedAt,
            },
          }),
        });
      } else {
        await airtableFetch("", {
          method: "POST",
          body: JSON.stringify({
            fields: {
              "Email":      email,
              "Status":     status,
              "Dashboard":  dashboard,
              "Period":     period,
              "Updated At": updatedAt,
            },
          }),
        });
      }

      return {
        statusCode: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ success: true }),
      };
    }

    return { statusCode: 405, headers: corsHeaders, body: "Method not allowed" };

  } catch (err) {
    console.error("Function error:", err);
    return {
      statusCode: 500,
      headers: corsHeaders,
      body: JSON.stringify({ success: false, error: err.message }),
    };
  }
};
