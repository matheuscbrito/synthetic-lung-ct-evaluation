// Glifo do workbench: quadrado preto arredondado de 44 px com a marca branca.
export function Logo() {
  return (
    <div className="logo">
      <svg viewBox="0 0 5 5" className="glyph" role="img" aria-label="QC Workbench">
        <path
          fillRule="evenodd"
          fill="#fff"
          d="M0 0h4v1H0zM4 1h1v1H4zM0 2h4v3H0zM1 3v1h2V3z"
        />
      </svg>
    </div>
  );
}
