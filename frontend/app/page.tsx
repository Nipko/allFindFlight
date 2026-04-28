"use client";

import { useState } from "react";

type Segment = {
  carrier: string;
  flight_number: string | null;
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  duration_minutes: number | null;
};

type Offer = {
  source: string;
  segments: Segment[];
  price: number;
  currency: string;
  booking_url: string | null;
};

type SearchResponse = {
  query: Record<string, unknown>;
  expanded_origins: string[];
  expanded_destinations: string[];
  offers: Offer[];
  sources_used: string[];
  sources_failed: string[];
};

export default function Home() {
  const [origin, setOrigin] = useState("MAD");
  const [destination, setDestination] = useState("BCN");
  const [departure, setDeparture] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [expand, setExpand] = useState(true);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        origin,
        destination,
        departure,
        adults: "1",
        expand_nearby: String(expand),
      });
      if (returnDate) params.set("return", returnDate);
      const res = await fetch(`/api/search?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 1100, margin: "40px auto", padding: "0 20px" }}>
      <h1 style={{ fontSize: 28, marginBottom: 4 }}>AllfindFlight</h1>
      <p style={{ color: "#8a8f96", marginBottom: 24 }}>
        Búsqueda inteligente con expansión a aeropuertos cercanos
      </p>

      <form
        onSubmit={search}
        style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}
      >
        <input
          value={origin}
          onChange={(e) => setOrigin(e.target.value.toUpperCase())}
          placeholder="Origen (IATA o ciudad)"
          style={{ flex: 1, minWidth: 160 }}
        />
        <input
          value={destination}
          onChange={(e) => setDestination(e.target.value.toUpperCase())}
          placeholder="Destino (IATA o ciudad)"
          style={{ flex: 1, minWidth: 160 }}
        />
        <input
          type="date"
          value={departure}
          onChange={(e) => setDeparture(e.target.value)}
          required
        />
        <input
          type="date"
          value={returnDate}
          onChange={(e) => setReturnDate(e.target.value)}
          placeholder="Vuelta (opcional)"
        />
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={expand} onChange={(e) => setExpand(e.target.checked)} />
          Aeropuertos cercanos
        </label>
        <button disabled={loading || !departure}>
          {loading ? "Buscando..." : "Buscar"}
        </button>
      </form>

      {error && <p style={{ color: "#e74c3c" }}>Error: {error}</p>}

      {data && (
        <>
          <p style={{ fontSize: 13, color: "#8a8f96" }}>
            Origen expandido: {data.expanded_origins.join(", ") || "(ninguno)"} ·
            Destino expandido: {data.expanded_destinations.join(", ") || "(ninguno)"}
          </p>
          <p style={{ fontSize: 13, color: "#8a8f96" }}>
            Fuentes OK: {data.sources_used.join(", ") || "ninguna"}
            {data.sources_failed.length > 0 && (
              <> · Fallaron: <span style={{ color: "#e67e22" }}>{data.sources_failed.join(", ")}</span></>
            )}
          </p>

          <p style={{ fontSize: 12, color: "#e67e22", marginTop: 12 }}>
            Aviso: precios mostrados sin equipaje facturado. Verifica fees finales en la aerolínea.
          </p>

          <table style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Fuente</th>
                <th>Ruta</th>
                <th>Aerolíneas</th>
                <th>Salida</th>
                <th>Llegada</th>
                <th>Escalas</th>
                <th style={{ textAlign: "right" }}>Precio</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.offers.map((o, i) => (
                <tr key={i}>
                  <td>{o.source}</td>
                  <td>
                    {o.segments[0].origin} → {o.segments[o.segments.length - 1].destination}
                  </td>
                  <td>{Array.from(new Set(o.segments.map((s) => s.carrier))).join(", ")}</td>
                  <td>{new Date(o.segments[0].departure).toLocaleString("es")}</td>
                  <td>
                    {new Date(o.segments[o.segments.length - 1].arrival).toLocaleString("es")}
                  </td>
                  <td>{o.segments.length - 1}</td>
                  <td style={{ textAlign: "right", fontWeight: 600 }}>
                    {o.price.toFixed(2)} {o.currency}
                  </td>
                  <td>
                    {o.booking_url && (
                      <a href={o.booking_url} target="_blank" rel="noopener">
                        Reservar →
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {data.offers.length === 0 && (
            <p style={{ marginTop: 24, color: "#8a8f96" }}>Sin resultados.</p>
          )}
        </>
      )}
    </main>
  );
}
