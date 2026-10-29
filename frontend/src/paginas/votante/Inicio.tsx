import { FileCheck2, Landmark, Settings, ShieldCheck } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { BigButton, Pantalla } from "../../componentes/ui";
import { useVotante } from "../../sesion";

export function Bienvenida() {
  const navegar = useNavigate();
  const { reiniciar } = useVotante();
  // Celular: una columna con el botón abajo. Escritorio (lg): presentación a la izquierda y acciones a la derecha.
  return (
    <Pantalla className="relative bg-primary text-white lg:bg-linear-to-br lg:from-primary-dark lg:to-primary">
      <nav aria-label="Accesos institucionales" className="absolute top-4 left-4 flex gap-2 lg:top-6 lg:left-8">
        <Link to="/admin"
          className="rounded-xl border-[1.5px] border-linea bg-white/90 px-3 py-2 text-xs font-bold text-primary shadow-lg">
          <Settings className="mr-1 inline size-3.5" />Admin
        </Link>
        {/* Simula la oficina de la Registraduría, donde el ciudadano se inscribe antes de votar. */}
        <Link to="/registraduria"
          className="rounded-xl border-[1.5px] border-linea bg-white/90 px-3 py-2 text-xs font-bold text-primary shadow-lg">
          <Landmark className="mr-1 inline size-3.5" />Registraduría
        </Link>
      </nav>
      <div className="contenido flex flex-1 flex-col lg:flex-row lg:items-center lg:gap-16 lg:px-10">
        <main className="flex flex-1 flex-col items-center justify-center px-6 pt-16 pb-8 text-center lg:items-start lg:p-0 lg:text-left">
          <div className="mb-6 flex size-24 items-center justify-center rounded-2xl bg-white shadow-2xl lg:size-28">
            <FileCheck2 className="size-13 text-primary lg:size-15" strokeWidth={1.6} />
          </div>
          <h1 className="text-4xl leading-[45px] font-black tracking-[-0.9px] lg:text-6xl lg:leading-[68px]">VotoSeguro</h1>
          <p className="pt-1 text-lg font-semibold text-info-borde lg:text-2xl">Colombia</p>
          <p className="mt-4 rounded-full bg-white/15 px-4 py-1.5 text-sm font-medium text-sobre-primario">
            Plataforma Oficial de Votación Electrónica
          </p>
          <p className="mt-8 max-w-[337px] leading-[26px] text-white/80 lg:max-w-lg lg:text-xl lg:leading-8">
            Su voto es secreto, seguro y está protegido con cifrado de extremo a extremo.
          </p>
          <ul className="flex gap-4 pt-6 text-xs font-semibold text-info-borde lg:text-sm">
            <li>🔒 Cifrado</li><li>✓ Verificable</li><li>🇨🇴 Oficial</li>
          </ul>
        </main>
        <footer className="px-6 pb-12 md:mx-auto md:w-full md:max-w-sm lg:mx-0 lg:max-w-md lg:shrink-0 lg:rounded-3xl lg:border-[1.5px] lg:border-white/20 lg:bg-white/10 lg:p-10 lg:shadow-2xl lg:backdrop-blur-lg">
          <div className="hidden pb-6 lg:block">
            <h2 className="text-2xl font-bold">Ejercer mi voto</h2>
            <p className="pt-2 text-sm leading-6 text-sobre-primario">
              Identifíquese con su documento y su rostro y elija su candidato. Si aún no está inscrito, hágalo primero
              en la Registraduría.
            </p>
          </div>
          <BigButton onClick={() => { reiniciar(); navegar("/identificacion"); }}>
            <ShieldCheck className="size-5.5" /> Iniciar Verificación
          </BigButton>
          <p className="pt-3 pb-2 text-center text-xs text-info-borde">
            Registrado por la Registraduría Nacional del Estado Civil
          </p>
          <Link to="/verificar" className="block text-center text-xs font-semibold text-white underline">
            Verificar un comprobante de votación
          </Link>
        </footer>
      </div>
    </Pantalla>
  );
}
