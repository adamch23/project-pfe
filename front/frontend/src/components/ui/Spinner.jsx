import React from "react";

const Spinner = ({ size = 14, color = "#fff" }) => {
  return (
    <span style={{
      display: "inline-block", 
      width: size, 
      height: size,
      border: `2px solid ${color}30`, 
      borderTopColor: color,
      borderRadius: "50%", 
      animation: "spin 0.7s linear infinite", 
      flexShrink: 0,
    }} />
  );
};

export default Spinner;
