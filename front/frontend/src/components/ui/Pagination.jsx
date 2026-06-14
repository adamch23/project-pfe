import React from "react";

const Pagination = ({ currentPage, totalPages, onPage, color }) => {
  if (totalPages <= 1) return null;
  
  const pages = [];
  let start = Math.max(1, currentPage - 2);
  let end   = Math.min(totalPages, start + 4);
  if (end - start < 4) start = Math.max(1, end - 4);
  for (let p = start; p <= end; p++) pages.push(p);

  const btnBase = {
    padding: "5px 11px", 
    borderRadius: "6px", 
    fontSize: "11px",
    cursor: "pointer", 
    border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.04)", 
    color: "#9ca3af",
    transition: "all 0.15s", 
    fontFamily: "inherit",
  };
  
  const disabled = { opacity: 0.3, cursor: "default", pointerEvents: "none" };

  return (
    <div style={{ display: "flex", gap: "5px", alignItems: "center", flexWrap: "wrap" }}>
      <button 
        onClick={() => onPage(1)} 
        disabled={currentPage === 1}
        style={{ ...btnBase, ...(currentPage === 1 ? disabled : {}) }}
      >
        «
      </button>
      <button 
        onClick={() => onPage(currentPage - 1)} 
        disabled={currentPage === 1}
        style={{ ...btnBase, ...(currentPage === 1 ? disabled : {}) }}
      >
        ‹ Préc.
      </button>
      
      {pages.map(p => (
        <button 
          key={p} 
          onClick={() => onPage(p)} 
          style={{
            ...btnBase,
            ...(p === currentPage ? { background: color, color: "#fff", border: "none", fontWeight: 700 } : {}),
          }}
        >
          {p}
        </button>
      ))}
      
      <button 
        onClick={() => onPage(currentPage + 1)} 
        disabled={currentPage >= totalPages}
        style={{ ...btnBase, ...(currentPage >= totalPages ? disabled : {}) }}
      >
        Suiv. ›
      </button>
      <button 
        onClick={() => onPage(totalPages)} 
        disabled={currentPage >= totalPages}
        style={{ ...btnBase, ...(currentPage >= totalPages ? disabled : {}) }}
      >
        »
      </button>
    </div>
  );
};

export default Pagination;
