import React, { useEffect, useMemo, useState } from "react";
import InfoTable from "./InfoTable";

const formatDateLocal = (dateObj) => {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, "0");
  const d = String(dateObj.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const parseDateLocal = (dateStr) => {
  if (!dateStr) return null;
  const dt = new Date(`${dateStr}T00:00:00`);
  return Number.isNaN(dt.getTime()) ? null : dt;
};

const toDraft = (entry) => {
  const snapshot = entry.snapshot || {};
  const kwh = snapshot.kwh_fees || {};
  const distribuce = kwh.distribuce || {};
  const fixed = snapshot.fixed || {};
  const daily = fixed.daily || {};
  const monthly = fixed.monthly || {};
  const prodej = snapshot.prodej || {};

  return {
    id: entry.effective_from,
    effective_from: entry.effective_from,
    effective_to: entry.effective_to || "",
    dph: snapshot.dph_percent == null ? "" : String(snapshot.dph_percent),
    poplatky: {
      komodita_sluzba: kwh.komodita_sluzba == null ? "" : String(kwh.komodita_sluzba),
      oze: kwh.oze == null ? "" : String(kwh.oze),
      dan: kwh.dan == null ? "" : String(kwh.dan),
      systemove_sluzby: kwh.systemove_sluzby == null ? "" : String(kwh.systemove_sluzby),
      distribuce: {
        NT: distribuce.NT == null ? "" : String(distribuce.NT),
        VT: distribuce.VT == null ? "" : String(distribuce.VT),
      },
    },
    fixni: {
      denni: {
        staly_plat: daily.staly_plat == null ? "" : String(daily.staly_plat),
      },
      mesicni: {
        provoz_nesitove_infrastruktury:
          monthly.provoz_nesitove_infrastruktury == null
            ? ""
            : String(monthly.provoz_nesitove_infrastruktury),
        jistic: monthly.jistic == null ? "" : String(monthly.jistic),
      },
    },
    prodej: {
      koeficient_snizeni_ceny:
        prodej.koeficient_snizeni_ceny == null ? "" : String(prodej.koeficient_snizeni_ceny),
    },
    isNew: false,
  };
};

const toNumber = (value) => {
  if (value == null || value === "") return 0;
  const normalized = String(value).replace(",", ".");
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
};

const toPayload = (draft) => {
  const payload = {
    effective_from: draft.effective_from,
    snapshot: {
      dph: toNumber(draft.dph),
      poplatky: {
        komodita_sluzba: toNumber(draft.poplatky.komodita_sluzba),
        oze: toNumber(draft.poplatky.oze),
        dan: toNumber(draft.poplatky.dan),
        systemove_sluzby: toNumber(draft.poplatky.systemove_sluzby),
        distribuce: {
          NT: toNumber(draft.poplatky.distribuce.NT),
          VT: toNumber(draft.poplatky.distribuce.VT),
        },
      },
      fixni: {
        denni: {
          staly_plat: toNumber(draft.fixni.denni.staly_plat),
        },
        mesicni: {
          provoz_nesitove_infrastruktury: toNumber(draft.fixni.mesicni.provoz_nesitove_infrastruktury),
          jistic: toNumber(draft.fixni.mesicni.jistic),
        },
      },
      prodej: {
        koeficient_snizeni_ceny: toNumber(draft.prodej.koeficient_snizeni_ceny),
      },
    },
  };
  if (draft.effective_to) {
    payload.effective_to = draft.effective_to;
  }
  return payload;
};

const FeesHistorySection = ({
  visible,
  onToggle,
  history,
  loading,
  error,
  onSave,
  defaultValues,
}) => {
  const [drafts, setDrafts] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [confirmCountdown, setConfirmCountdown] = useState(0);
  const [validationError, setValidationError] = useState(null);
  const todayStr = useMemo(() => formatDateLocal(new Date()), []);
  const todayDate = useMemo(() => parseDateLocal(todayStr), [todayStr]);

  useEffect(() => {
    setDrafts(history.map(toDraft));
    setEditingId(null);
    setConfirmDeleteId(null);
    setConfirmCountdown(0);
    setValidationError(null);
  }, [history]);

  const sortedDrafts = useMemo(() => {
    return [...drafts].sort((a, b) => {
      const da = parseDateLocal(a.effective_from);
      const db = parseDateLocal(b.effective_from);
      if (!da && !db) return 0;
      if (!da) return -1;
      if (!db) return 1;
      return da - db;
    });
  }, [drafts]);

  const ranges = useMemo(() => {
    const validEntries = sortedDrafts.filter((entry) => parseDateLocal(entry.effective_from));
    const rangeMap = {};
    validEntries.forEach((entry, idx) => {
      const next = validEntries[idx + 1];
      let validTo = entry.effective_to || null;
      if (!validTo && next) {
        const nextDate = parseDateLocal(next.effective_from);
        if (nextDate) {
          nextDate.setDate(nextDate.getDate() - 1);
          validTo = formatDateLocal(nextDate);
        }
      }
      const fromDate = parseDateLocal(entry.effective_from);
      const toDate = validTo ? parseDateLocal(validTo) : null;
      const isCurrent =
        !!fromDate &&
        !!todayDate &&
        fromDate <= todayDate &&
        (!toDate || todayDate <= toDate);
      rangeMap[entry.id] = {
        valid_to: validTo,
        is_current: isCurrent,
      };
    });
    return rangeMap;
  }, [sortedDrafts, todayDate]);

  const updateDraft = (id, updater) => {
    setConfirmDeleteId(null);
    setConfirmCountdown(0);
    setDrafts((prev) =>
      prev.map((draft) => (draft.id === id ? { ...draft, ...updater(draft) } : draft))
    );
  };

  const buildPayload = (entries) => {
    return entries.filter((entry) => entry.effective_from).map((entry) => toPayload(entry));
  };

  const validateDrafts = (entries) => {
    const seen = new Set();
    const candidates = entries.filter((entry) => entry.effective_from);
    if (candidates.length === 0) {
      return "Historie nesmi byt prazdna.";
    }
    const parsedEntries = [];
    for (const entry of candidates) {
      const parsedFrom = parseDateLocal(entry.effective_from);
      if (!parsedFrom) {
        return `Neplatne datum: ${entry.effective_from}`;
      }
      let parsedTo = null;
      if (entry.effective_to) {
        parsedTo = parseDateLocal(entry.effective_to);
        if (!parsedTo) {
          return `Neplatne datum: ${entry.effective_to}`;
        }
        if (parsedTo < parsedFrom) {
          return "Platne do musi byt stejne nebo pozdeji nez Platne od.";
        }
      }
      if (seen.has(entry.effective_from)) {
        return `Duplicita data Platne od: ${entry.effective_from}`;
      }
      seen.add(entry.effective_from);
      parsedEntries.push({ id: entry.id, from: parsedFrom, to: parsedTo });
    }
    parsedEntries.sort((a, b) => a.from - b.from);
    for (let i = 0; i < parsedEntries.length - 1; i += 1) {
      const current = parsedEntries[i];
      const next = parsedEntries[i + 1];
      let currentTo = current.to;
      if (!currentTo) {
        currentTo = new Date(next.from.getTime());
        currentTo.setDate(currentTo.getDate() - 1);
      }
      if (currentTo < current.from) {
        return "Platne do musi byt stejne nebo pozdeji nez Platne od.";
      }
      if (currentTo >= next.from) {
        return "Rozsahy poplatku se prekryvaji. Uprav Platne do/od.";
      }
    }
    return null;
  };

  const handleAdd = () => {
    const base = defaultValues || {
      dph: "",
      poplatky: {
        komodita_sluzba: "",
        oze: "",
        dan: "",
        systemove_sluzby: "",
        distribuce: { NT: "", VT: "" },
      },
      fixni: {
        denni: { staly_plat: "" },
        mesicni: { provoz_nesitove_infrastruktury: "", jistic: "" },
      },
      prodej: {
        koeficient_snizeni_ceny: "",
      },
    };
    const newId = `new-${Date.now()}`;
    const prevYear = new Date().getFullYear() - 1;
    const newEntry = {
      id: newId,
      effective_from: `${prevYear}-01-01`,
      effective_to: `${prevYear}-12-31`,
      dph: base.dph ?? "",
      poplatky: {
        komodita_sluzba: base.poplatky.komodita_sluzba ?? "",
        oze: base.poplatky.oze ?? "",
        dan: base.poplatky.dan ?? "",
        systemove_sluzby: base.poplatky.systemove_sluzby ?? "",
        distribuce: {
          NT: base.poplatky.distribuce.NT ?? "",
          VT: base.poplatky.distribuce.VT ?? "",
        },
      },
      fixni: {
        denni: { staly_plat: base.fixni.denni.staly_plat ?? "" },
        mesicni: {
          provoz_nesitove_infrastruktury: base.fixni.mesicni.provoz_nesitove_infrastruktury ?? "",
          jistic: base.fixni.mesicni.jistic ?? "",
        },
      },
      prodej: {
        koeficient_snizeni_ceny: base.prodej?.koeficient_snizeni_ceny ?? "",
      },
      isNew: true,
    };
    setDrafts((prev) => [newEntry, ...prev]);
    setEditingId(newId);
    setConfirmDeleteId(null);
    setConfirmCountdown(0);
    setValidationError(null);
  };

  const handleCancel = () => {
    setDrafts(history.map(toDraft));
    setEditingId(null);
    setConfirmDeleteId(null);
    setConfirmCountdown(0);
    setValidationError(null);
  };

  const handleSave = (id) => {
    const validation = validateDrafts(drafts);
    if (validation) {
      setValidationError(validation);
      return;
    }
    setValidationError(null);
    const payload = buildPayload(drafts);
    onSave(payload).then(() => {
      setEditingId(null);
    });
  };

  const handleDelete = (id) => {
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id);
      setConfirmCountdown(5);
      return;
    }
    if (confirmCountdown > 0) {
      return;
    }
    const nextDrafts = drafts.filter((entry) => entry.id !== id);
    const validation = validateDrafts(nextDrafts);
    if (validation) {
      setValidationError(validation);
      setConfirmDeleteId(null);
      setConfirmCountdown(0);
      return;
    }
    setValidationError(null);
    const payload = buildPayload(nextDrafts);
    onSave(payload).then(() => {
      setConfirmDeleteId(null);
      setConfirmCountdown(0);
    });
  };

  useEffect(() => {
    if (!confirmDeleteId || confirmCountdown <= 0) {
      return;
    }
    const timer = setTimeout(() => {
      setConfirmCountdown((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearTimeout(timer);
  }, [confirmDeleteId, confirmCountdown]);

  if (!visible) {
    return (
      <div className="config-actions">
        <button onClick={onToggle}>Historie poplatku</button>
      </div>
    );
  }

  return (
    <div className="fees-history">
      <div className="fees-history-header">
        <div>
          <h4>Historie poplatku</h4>
          <div className="config-muted">Upravuj pouze historicke zaznamy. Aktualni poplatky se meni v konfiguraci.</div>
        </div>
        <div className="fees-history-actions">
          <button onClick={handleAdd}>Pridat obdobi</button>
          <button onClick={onToggle}>Skryt historii</button>
        </div>
      </div>

      {loading && <div className="config-muted">Nacitam historii...</div>}
      {error && <div className="alert error">{error}</div>}
      {validationError && <div className="alert error">{validationError}</div>}

      {!loading && !error && sortedDrafts.length === 0 && (
        <div className="config-muted">Historie poplatku neni k dispozici.</div>
      )}

      <div className="fees-history-list">
        {sortedDrafts.map((entry) => {
          const rangeInfo = ranges[entry.id] || {};
          const validTo = rangeInfo.valid_to || "nyni";
          const isCurrent = rangeInfo.is_current;
          const isEditing = editingId === entry.id;
          const canManage = !isCurrent;
          const dateMax = todayStr;
          const effectiveToValue =
            entry.effective_to || (validTo !== "nyni" ? validTo : "");

          const rows = [
            { label: "DPH", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.dph}
                onChange={(e) => updateDraft(entry.id, (draft) => ({ dph: e.target.value }))}
              />
            ) : entry.dph, unit: "%" },
            { label: "Sluzba obchodu", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.poplatky.komodita_sluzba}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    poplatky: { ...draft.poplatky, komodita_sluzba: e.target.value },
                  }))
                }
              />
            ) : entry.poplatky.komodita_sluzba, unit: "Kc/kWh" },
            { label: "OZE", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.poplatky.oze}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    poplatky: { ...draft.poplatky, oze: e.target.value },
                  }))
                }
              />
            ) : entry.poplatky.oze, unit: "Kc/kWh" },
            { label: "Dan", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.poplatky.dan}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    poplatky: { ...draft.poplatky, dan: e.target.value },
                  }))
                }
              />
            ) : entry.poplatky.dan, unit: "Kc/kWh" },
            { label: "Systemove sluzby", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.poplatky.systemove_sluzby}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    poplatky: { ...draft.poplatky, systemove_sluzby: e.target.value },
                  }))
                }
              />
            ) : entry.poplatky.systemove_sluzby, unit: "Kc/kWh" },
            { label: "Distribuce NT", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.poplatky.distribuce.NT}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    poplatky: {
                      ...draft.poplatky,
                      distribuce: { ...draft.poplatky.distribuce, NT: e.target.value },
                    },
                  }))
                }
              />
            ) : entry.poplatky.distribuce.NT, unit: "Kc/kWh" },
            { label: "Distribuce VT", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.poplatky.distribuce.VT}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    poplatky: {
                      ...draft.poplatky,
                      distribuce: { ...draft.poplatky.distribuce, VT: e.target.value },
                    },
                  }))
                }
              />
            ) : entry.poplatky.distribuce.VT, unit: "Kc/kWh" },
            { label: "Staly plat", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.fixni.denni.staly_plat}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    fixni: { ...draft.fixni, denni: { staly_plat: e.target.value } },
                  }))
                }
              />
            ) : entry.fixni.denni.staly_plat, unit: "Kc/den" },
            { label: "Nesitova infrastruktura", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.fixni.mesicni.provoz_nesitove_infrastruktury}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    fixni: {
                      ...draft.fixni,
                      mesicni: {
                        ...draft.fixni.mesicni,
                        provoz_nesitove_infrastruktury: e.target.value,
                      },
                    },
                  }))
                }
              />
            ) : entry.fixni.mesicni.provoz_nesitove_infrastruktury, unit: "Kc/mesic" },
            { label: "Jistic", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.fixni.mesicni.jistic}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    fixni: {
                      ...draft.fixni,
                      mesicni: {
                        ...draft.fixni.mesicni,
                        jistic: e.target.value,
                      },
                    },
                  }))
                }
              />
            ) : entry.fixni.mesicni.jistic, unit: "Kc/mesic" },
            { label: "Koeficient snizeni", value: isEditing ? (
              <input
                type="text"
                inputMode="decimal"
                value={entry.prodej.koeficient_snizeni_ceny}
                onChange={(e) =>
                  updateDraft(entry.id, (draft) => ({
                    prodej: {
                      ...draft.prodej,
                      koeficient_snizeni_ceny: e.target.value,
                    },
                  }))
                }
              />
            ) : entry.prodej.koeficient_snizeni_ceny, unit: "Kc/MWh" },
          ];

          return (
            <div className="fees-history-card" key={entry.id}>
              <div className="fees-history-meta">
                <div>
                  Platne od:{" "}
                  {isEditing ? (
                    <input
                      type="date"
                      value={entry.effective_from}
                      max={dateMax}
                      onChange={(e) => updateDraft(entry.id, () => ({ effective_from: e.target.value }))}
                    />
                  ) : (
                    entry.effective_from
                  )}
                </div>
                <div>
                  Platne do:{" "}
                  {isEditing && canManage ? (
                    <input
                      type="date"
                      value={effectiveToValue}
                      max={dateMax}
                      onChange={(e) => updateDraft(entry.id, () => ({ effective_to: e.target.value }))}
                    />
                  ) : (
                    validTo
                  )}
                </div>
              </div>
              <InfoTable rows={rows} valueAlign="right" headerValueAlign="right" />
              <div className="fees-history-actions">
                {!isEditing && canManage && (
                  <button
                    onClick={() => {
                      setConfirmDeleteId(null);
                      if (!entry.effective_to && validTo !== "nyni") {
                        updateDraft(entry.id, () => ({ effective_to: validTo }));
                      }
                      setEditingId(entry.id);
                    }}
                  >
                    Upravit
                  </button>
                )}
                {!isEditing && canManage && (
                  <>
                    {confirmDeleteId !== entry.id ? (
                      <button onClick={() => handleDelete(entry.id)}>
                        Smazat
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={() => handleDelete(entry.id)}
                          className={`danger-button${confirmCountdown === 0 ? " is-ready" : ""}`}
                          disabled={confirmCountdown > 0}
                        >
                          {confirmCountdown > 0 ? `Potvrdit smazani (${confirmCountdown}s)` : "Potvrdit smazani"}
                        </button>
                        <button onClick={() => { setConfirmDeleteId(null); setConfirmCountdown(0); }}>
                          Zrusit
                        </button>
                      </>
                    )}
                  </>
                )}
                {isEditing && (
                  <>
                    <button onClick={() => handleSave(entry.id)}>Ulozit</button>
                    <button onClick={handleCancel}>Zrusit</button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default FeesHistorySection;
