import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import "./index.css";
import { CandidatosAdmin } from "./paginas/admin/Candidatos";
import { Dashboard } from "./paginas/admin/Dashboard";
import { AdminLayout, LoginAdmin } from "./paginas/admin/Layout";
import { Auditoria, Cuentas, Historial, Mas, Monitoreo, Respaldos, Votantes } from "./paginas/admin/Mas";
import { ResultadosAdmin } from "./paginas/admin/Resultados";
import { Votaciones } from "./paginas/admin/Votaciones";
import { Inscripcion } from "./paginas/registraduria/Inscripcion";
import { Biometria, Elegibilidad, Identificacion } from "./paginas/votante/Identificacion";
import { Bienvenida } from "./paginas/votante/Inicio";
import { Bloqueado, ResultadosPublicos, VerificarComprobante } from "./paginas/votante/Publico";
import { Candidatos, ComprobanteVoto, Confirmar, Elecciones, Gracias } from "./paginas/votante/Votacion";
import { ProveedorAdmin, ProveedorVotante } from "./sesion";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ProveedorVotante>
        <ProveedorAdmin>
          <Routes>
            <Route path="/" element={<Bienvenida />} />
            <Route path="/registraduria" element={<Inscripcion />} />
            <Route path="/identificacion" element={<Identificacion />} />
            <Route path="/biometria" element={<Biometria />} />
            <Route path="/elegibilidad" element={<Elegibilidad />} />
            <Route path="/bloqueado" element={<Bloqueado />} />
            <Route path="/elecciones" element={<Elecciones />} />
            <Route path="/candidatos" element={<Candidatos />} />
            <Route path="/confirmar" element={<Confirmar />} />
            <Route path="/comprobante" element={<ComprobanteVoto />} />
            <Route path="/gracias" element={<Gracias />} />
            <Route path="/verificar" element={<VerificarComprobante />} />
            <Route path="/resultados/:id" element={<ResultadosPublicos />} />

            <Route path="/admin" element={<LoginAdmin />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="votaciones" element={<Votaciones />} />
              <Route path="candidatos" element={<CandidatosAdmin />} />
              <Route path="resultados" element={<ResultadosAdmin />} />
              <Route path="mas" element={<Mas />} />
              <Route path="auditoria" element={<Auditoria />} />
              <Route path="respaldos" element={<Respaldos />} />
              <Route path="cuentas" element={<Cuentas />} />
              <Route path="historial" element={<Historial />} />
              <Route path="votantes" element={<Votantes />} />
              <Route path="monitoreo" element={<Monitoreo />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ProveedorAdmin>
      </ProveedorVotante>
    </BrowserRouter>
  </StrictMode>,
);
