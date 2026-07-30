"use client";

import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float, MeshDistortMaterial } from "@react-three/drei";
import * as THREE from "three";

/* ─── Floating geometric shapes ─── */

function Shapes({ mouse }: { mouse: { x: number; y: number } }) {
  const group = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (!group.current) return;
    group.current.rotation.y += delta * 0.04;
    group.current.rotation.x += delta * 0.02;
    group.current.position.x += (mouse.x * 0.3 - group.current.position.x) * 0.02;
    group.current.position.y += (-mouse.y * 0.3 - group.current.position.y) * 0.02;
  });

  const shapes = useMemo(() => {
    const arr: { pos: [number, number, number]; scale: number; color: string; type: "octa" | "torus" | "icosa" | "cylinder" }[] = [];
    const colors = ["#6366f1", "#a855f7", "#06b6d4", "#8b5cf6", "#3b82f6"];
    for (let i = 0; i < 30; i++) {
      arr.push({
        pos: [
          (Math.random() - 0.5) * 14,
          (Math.random() - 0.5) * 10,
          (Math.random() - 0.5) * 8 - 2,
        ],
        scale: 0.08 + Math.random() * 0.15,
        color: colors[i % colors.length],
        type: ["octa", "torus", "icosa", "cylinder"][Math.floor(Math.random() * 4)] as any,
      });
    }
    return arr;
  }, []);

  return (
    <group ref={group}>
      {shapes.map((s, i) => (
        <Float key={i} speed={0.4 + Math.random() * 0.6} rotationIntensity={0.8} floatIntensity={0.6}>
          <mesh position={s.pos} scale={s.scale}>
            {s.type === "octa" && <octahedronGeometry args={[1, 1]} />}
            {s.type === "torus" && <torusKnotGeometry args={[0.8, 0.3, 64, 8]} />}
            {s.type === "icosa" && <icosahedronGeometry args={[1, 1]} />}
            {s.type === "cylinder" && <cylinderGeometry args={[0.6, 0.6, 1, 6]} />}
            <MeshDistortMaterial
              color={s.color}
              emissive={s.color}
              emissiveIntensity={0.15}
              roughness={0.2}
              metalness={0.6}
              wireframe={i % 3 === 0}
              transparent
              opacity={0.7}
              distort={0.15}
            />
          </mesh>
        </Float>
      ))}
    </group>
  );
}

/* ─── Particle field ─── */

function Particles({ count = 600 }) {
  const ref = useRef<THREE.Points>(null);
  const { pointer } = useThree();

  const [positions, colors] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    const palette = [
      new THREE.Color("#6366f1"),
      new THREE.Color("#a855f7"),
      new THREE.Color("#06b6d4"),
      new THREE.Color("#8b5cf6"),
    ];
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 15;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 15;
      const c = palette[Math.floor(Math.random() * palette.length)];
      col[i * 3] = c.r;
      col[i * 3 + 1] = c.g;
      col[i * 3 + 2] = c.b;
    }
    return [pos, col];
  }, [count]);

  useFrame((_, delta) => {
    if (!ref.current) return;
    const positions = ref.current.geometry.attributes.position.array as Float32Array;
    for (let i = 0; i < count; i++) {
      positions[i * 3 + 1] += Math.sin(Date.now() * 0.0005 + i) * 0.001;
      positions[i * 3] += Math.cos(Date.now() * 0.0003 + i * 0.5) * 0.001;
    }
    ref.current.geometry.attributes.position.needsUpdate = true;
    ref.current.rotation.y += delta * 0.005;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-color"
          count={count}
          array={colors}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.04}
        vertexColors
        transparent
        opacity={0.8}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        sizeAttenuation
      />
    </points>
  );
}

/* ─── Main Scene ─── */

function Scene({ mouse }: { mouse: { x: number; y: number } }) {
  return (
    <>
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 5, 5]} intensity={0.8} />
      <directionalLight position={[-5, -3, -5]} intensity={0.3} color="#6366f1" />
      <Shapes mouse={mouse} />
      <Particles count={500} />
    </>
  );
}

/* ─── Exported Component ─── */

export default function ThreeBackground() {
  const mouse = useRef({ x: 0, y: 0 });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(true);
    const handleMove = (e: MouseEvent) => {
      mouse.current = {
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: -(e.clientY / window.innerHeight) * 2 + 1,
      };
    };
    window.addEventListener("mousemove", handleMove);
    return () => window.removeEventListener("mousemove", handleMove);
  }, []);

  if (!ready) return null;

  return (
    <div className="fixed inset-0 -z-10 pointer-events-none" style={{ perspective: "1000px" }}>
      <Canvas
        camera={{ position: [0, 0, 6], fov: 60 }}
        dpr={[1, 1.5]}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: "low-power",
        }}
        style={{ background: "transparent", width: "100%", height: "100%" }}
      >
        <Scene mouse={{ x: mouse.current.x, y: mouse.current.y }} />
      </Canvas>
    </div>
  );
}
