"use client";

import { useMemo, useRef, useEffect, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Float } from "@react-three/drei";
import * as THREE from "three";
import { useTheme } from "@/components/ThemeProvider";

type Point = [number, number, number];

type NetworkNode = {
  position: Point;
  size: number;
  color: string;
  kind: "core" | "edge";
};

const NETWORK_POINTS: Point[] = [
  [-3.4, 1.4, -1.5],
  [-2.1, 2.2, -2.2],
  [-1.2, 0.6, -1],
  [0, 1.7, -2.6],
  [1.7, 2.5, -1.6],
  [2.8, 1.1, -2.8],
  [3.5, -0.4, -1.8],
  [2.1, -1.7, -2.2],
  [0.4, -1.2, -1.2],
  [-1.6, -1.6, -2.5],
  [-3.1, -0.4, -1.4],
  [-0.1, 0.1, -0.3],
];

const NETWORK_EDGES: [number, number][] = [
  [0, 1],
  [0, 2],
  [1, 3],
  [2, 3],
  [2, 9],
  [2, 11],
  [3, 4],
  [3, 11],
  [4, 5],
  [4, 11],
  [5, 6],
  [5, 7],
  [6, 7],
  [7, 8],
  [8, 9],
  [8, 11],
  [9, 10],
  [10, 0],
  [10, 11],
];

function Network({ mouse, primaryColor }: { mouse: { x: number; y: number }; primaryColor: string }) {
  const group = useRef<THREE.Group>(null);
  const nodes = useMemo<NetworkNode[]>(
    () =>
      NETWORK_POINTS.map((position, index) => ({
        position,
        size: index === NETWORK_POINTS.length - 1 ? 0.22 : 0.07 + (index % 3) * 0.025,
        color: primaryColor,
        kind: index === NETWORK_POINTS.length - 1 ? "core" : "edge",
      })),
    [primaryColor]
  );

  const edgePositions = useMemo(() => {
    const values = new Float32Array(NETWORK_EDGES.length * 2 * 3);
    NETWORK_EDGES.forEach(([from, to], index) => {
      values.set(NETWORK_POINTS[from], index * 6);
      values.set(NETWORK_POINTS[to], index * 6 + 3);
    });
    return values;
  }, []);

  useFrame((_, delta) => {
    if (!group.current) return;
    group.current.rotation.y += delta * 0.035;
    group.current.rotation.x += delta * 0.008;
    group.current.position.x += (mouse.x * 0.22 - group.current.position.x) * 0.025;
    group.current.position.y += (mouse.y * 0.12 - group.current.position.y) * 0.025;
  });

  return (
    <group ref={group}>
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            array={edgePositions}
            count={edgePositions.length / 3}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial color={primaryColor} transparent opacity={0.16} depthWrite={false} />
      </lineSegments>

      {nodes.map((node, index) => (
        <Float
          key={index}
          speed={node.kind === "core" ? 1.1 : 0.45 + (index % 3) * 0.12}
          rotationIntensity={0.18}
          floatIntensity={node.kind === "core" ? 0.35 : 0.12}
        >
          <mesh position={node.position}>
            {node.kind === "core" ? (
              <icosahedronGeometry args={[node.size, 2]} />
            ) : (
              <sphereGeometry args={[node.size, 12, 12]} />
            )}
            <meshStandardMaterial
              color={node.color}
              emissive={primaryColor}
              emissiveIntensity={node.kind === "core" ? 0.75 : 0.35}
              metalness={0.65}
              roughness={0.28}
              transparent
              opacity={node.kind === "core" ? 0.9 : 0.62}
            />
          </mesh>
        </Float>
      ))}
    </group>
  );
}

function Particles({ primaryColor }: { primaryColor: string }) {
  const ref = useRef<THREE.Points>(null);
  const { pointer } = useThree();
  const count = 280;
  const [positions, colors] = useMemo(() => {
    const positionValues = new Float32Array(count * 3);
    const colorValues = new Float32Array(count * 3);
    const color = new THREE.Color(primaryColor);
    for (let index = 0; index < count; index += 1) {
      positionValues[index * 3] = (index % 28 - 14) * 0.62;
      positionValues[index * 3 + 1] = (Math.floor(index / 28) - 5) * 0.62;
      positionValues[index * 3 + 2] = -3.5 - (index % 7) * 0.35;
      colorValues[index * 3] = color.r;
      colorValues[index * 3 + 1] = color.g;
      colorValues[index * 3 + 2] = color.b;
    }
    return [positionValues, colorValues];
  }, [primaryColor]);

  useFrame((_, delta) => {
    if (!ref.current) return;
    ref.current.rotation.y += delta * 0.008;
    ref.current.position.x += (pointer.x * 0.15 - ref.current.position.x) * 0.01;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={count} array={positions} itemSize={3} />
        <bufferAttribute attach="attributes-color" count={count} array={colors} itemSize={3} />
      </bufferGeometry>
      <pointsMaterial
        size={0.025}
        vertexColors
        transparent
        opacity={0.42}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        sizeAttenuation
      />
    </points>
  );
}

function Scene({ mouse, primaryColor }: { mouse: { x: number; y: number }; primaryColor: string }) {
  return (
    <>
      <ambientLight intensity={0.22} />
      <pointLight position={[2, 3, 3]} intensity={1.1} color={primaryColor} />
      <pointLight position={[-4, -2, 1]} intensity={0.55} color="#22d3ee" />
      <Network mouse={mouse} primaryColor={primaryColor} />
      <Particles primaryColor={primaryColor} />
    </>
  );
}

export default function ThreeBackground() {
  const { resolvedPrimary } = useTheme();
  const mouse = useRef({ x: 0, y: 0 });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(true);
    const handleMove = (event: MouseEvent) => {
      mouse.current = {
        x: (event.clientX / window.innerWidth) * 2 - 1,
        y: -(event.clientY / window.innerHeight) * 2 + 1,
      };
    };
    window.addEventListener("mousemove", handleMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMove);
  }, []);

  if (!ready) return null;

  return (
    <div className="aeon-3d-canvas" aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0, 6], fov: 58 }}
        dpr={[1, 1.35]}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
        style={{ background: "transparent", width: "100%", height: "100%" }}
      >
        <Scene mouse={mouse.current} primaryColor={resolvedPrimary} />
      </Canvas>
    </div>
  );
}
