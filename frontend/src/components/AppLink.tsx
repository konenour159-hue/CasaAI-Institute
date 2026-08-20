import { Link as RouterLink, NavLink as RouterNavLink, type LinkProps, type NavLinkProps } from "react-router-dom";

/** Remplace `Link`/`NavLink` de react-router-dom : identiques en tout point,
 * mais activent la View Transitions API du navigateur à chaque navigation
 * (fondu de continuité entre deux pages au lieu d'un remplacement instantané
 * du DOM). Centralisé ici pour ne pas répéter `viewTransition` sur chaque
 * lien du site — voir audit UX §2.1 et §4 "Maintenant".
 *
 * Dégradation automatique et sans code supplémentaire : react-router-dom ne
 * déclenche la transition que si `document.startViewTransition` existe côté
 * navigateur, sinon la navigation reste une simple navigation classique. Le
 * ralenti global sous `prefers-reduced-motion` est géré en CSS (index.css). */
export function Link(props: LinkProps) {
  return <RouterLink viewTransition {...props} />;
}

export function NavLink(props: NavLinkProps) {
  return <RouterNavLink viewTransition {...props} />;
}
