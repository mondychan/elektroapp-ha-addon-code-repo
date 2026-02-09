import React from "react";

const alignClass = (align) => {
  if (align === "left") return "cell-left";
  if (align === "center") return "cell-center";
  return "cell-right";
};

const InfoTable = ({
  rows,
  valueAlign = "right",
  headerValueAlign,
  unitAlign = "left",
  showHeader = true,
  showUnit = true,
}) => {
  const headerValueAlignClass = alignClass(headerValueAlign || valueAlign);
  const unitAlignClass = alignClass(unitAlign);
  const tableLayoutClass = showUnit ? "info-table--three" : "info-table--two";

  return (
    <table className={`data-table info-table table-fixed table-spaced-sm ${tableLayoutClass}`}>
      <colgroup>
        <col className="info-col-label" />
        <col className="info-col-value" />
        {showUnit && <col className="info-col-unit" />}
      </colgroup>
      {showHeader && (
        <thead>
          <tr>
            <th className="cell-left">Polozka</th>
            <th className={headerValueAlignClass}>{showUnit ? "Hodnota" : ""}</th>
            {showUnit && <th className="cell-left">Jednotka</th>}
          </tr>
        </thead>
      )}
      <tbody>
        {rows.map((row) => {
          const rowAlignClass = alignClass(row.valueAlign || valueAlign);
          const wrapClass = row.valueWrap ? "cell-wrap" : "cell-nowrap";
          return (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td className={`${rowAlignClass} ${wrapClass}`}>{row.value}</td>
              {showUnit && <td className={`${unitAlignClass} cell-nowrap`}>{row.unit || ""}</td>}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

export default InfoTable;
