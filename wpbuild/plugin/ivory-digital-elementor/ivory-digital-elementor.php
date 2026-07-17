<?php
/**
 * Plugin Name:       Ivory Digital - Website (Elementor)
 * Description:        Imports the full Ivory Digital website (all 22 pages) as Elementor-editable pages with pixel-exact design, full SEO, schema, robots.txt, sitemap.xml and llms.txt. Requires Elementor.
 * Version:           1.4.0
 * Author:            Ivory Digital
 * License:           GPL-2.0+
 * Text Domain:       ivory-digital
 * Requires Plugins:  elementor
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'IVORY_DIR', plugin_dir_path( __FILE__ ) );
define( 'IVORY_URL', plugin_dir_url( __FILE__ ) );
define( 'IVORY_BASE_URL', rtrim( IVORY_URL, '/' ) );          // plugin base (no trailing /assets)
define( 'IVORY_ASSETS_URL', IVORY_BASE_URL . '/assets' );      // for direct enqueues
define( 'IVORY_BASE_TOKEN', '__IVORY_BASE__' );                // markup already contains /assets/
define( 'IVORY_MAP_OPTION', 'ivory_imported_map' );
define( 'IVORY_VERSION', '1.4.0' );
define( 'IVORY_VER_OPTION', 'ivory_plugin_version' );

function ivory_elementor_active() {
	return did_action( 'elementor/loaded' ) || defined( 'ELEMENTOR_VERSION' );
}

function ivory_read_json( $rel ) {
	$path = IVORY_DIR . $rel;
	if ( ! file_exists( $path ) ) {
		return null;
	}
	return json_decode( file_get_contents( $path ), true );
}

function ivory_manifest() {
	$m = ivory_read_json( 'data/manifest.json' );
	return $m ? $m : array( 'order' => array(), 'pages' => array() );
}

function ivory_seo_map() {
	static $seo = null;
	if ( $seo === null ) {
		$seo = ivory_read_json( 'data/seo.json' );
		if ( ! is_array( $seo ) ) {
			$seo = array();
		}
	}
	return $seo;
}

/* ---------------- Import ---------------- */

function ivory_apply_elementor_meta( $post_id, $content, $page_settings ) {
	$json = wp_json_encode( $content );
	// token -> plugin base url (markup keeps its own /assets/ path -> single /assets/)
	$json = str_replace( IVORY_BASE_TOKEN, IVORY_BASE_URL, $json );

	update_post_meta( $post_id, '_elementor_data', wp_slash( $json ) );
	update_post_meta( $post_id, '_elementor_edit_mode', 'builder' );
	update_post_meta( $post_id, '_elementor_template_type', 'wp-page' );
	update_post_meta( $post_id, '_wp_page_template', 'elementor_canvas' );
	if ( defined( 'ELEMENTOR_VERSION' ) ) {
		update_post_meta( $post_id, '_elementor_version', ELEMENTOR_VERSION );
	}
	if ( ! empty( $page_settings ) ) {
		update_post_meta( $post_id, '_elementor_page_settings', $page_settings );
	}
}

function ivory_import_all( $force = false ) {
	if ( ! ivory_elementor_active() ) {
		return new WP_Error( 'no-elementor', 'Elementor is not active.' );
	}

	$manifest = ivory_manifest();
	$map      = get_option( IVORY_MAP_OPTION, array() );
	if ( ! is_array( $map ) ) {
		$map = array();
	}

	foreach ( $manifest['order'] as $slug ) {
		$doc = ivory_read_json( 'templates/' . $slug . '.json' );
		if ( ! $doc || empty( $doc['content'] ) ) {
			continue;
		}

		$existing = isset( $map[ $slug ] ) ? get_post( $map[ $slug ] ) : null;
		if ( $existing && ! $force ) {
			continue;
		}

		if ( $existing && $force ) {
			$post_id = $existing->ID;
			wp_update_post( array( 'ID' => $post_id, 'post_title' => $doc['title'] ) );
		} else {
			$post_id = wp_insert_post( array(
				'post_title'  => $doc['title'],
				'post_name'   => $slug,
				'post_status' => 'publish',
				'post_type'   => 'page',
			) );
		}

		if ( is_wp_error( $post_id ) || ! $post_id ) {
			continue;
		}

		$page_settings = isset( $doc['page_settings'] ) ? $doc['page_settings'] : array();
		ivory_apply_elementor_meta( $post_id, $doc['content'], $page_settings );
		$map[ $slug ] = $post_id;
	}

	update_option( IVORY_MAP_OPTION, $map );

	if ( ! empty( $map['home'] ) ) {
		update_option( 'show_on_front', 'page' );
		update_option( 'page_on_front', $map['home'] );
	}

	if ( ! get_option( 'permalink_structure' ) ) {
		update_option( 'permalink_structure', '/%postname%/' );
	}
	flush_rewrite_rules();

	if ( class_exists( '\Elementor\Plugin' ) ) {
		try {
			\Elementor\Plugin::$instance->files_manager->clear_cache();
		} catch ( \Throwable $e ) {}
	}

	return $map;
}

register_activation_hook( __FILE__, function () {
	if ( ivory_elementor_active() ) {
		// Force a full refresh so a version update replaces older (possibly broken) pages.
		$prev = get_option( IVORY_VER_OPTION );
		$force = ( $prev !== IVORY_VERSION );
		ivory_import_all( $force );
		update_option( IVORY_VER_OPTION, IVORY_VERSION );
	}
	flush_rewrite_rules();
} );

// Also refresh on normal load if the stored version is older than the plugin (covers updates
// applied without a fresh activation).
add_action( 'init', function () {
	if ( ! is_admin() || ! ivory_elementor_active() ) {
		return;
	}
	if ( get_option( IVORY_VER_OPTION ) !== IVORY_VERSION ) {
		ivory_import_all( true );
		update_option( IVORY_VER_OPTION, IVORY_VERSION );
	}
}, 5 );

/* ---------------- Front-end assets ---------------- */

add_action( 'wp_enqueue_scripts', function () {
	wp_enqueue_style( 'ivory-fonts', 'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Jost:wght@300;400;500&display=swap', array(), null );
	wp_enqueue_style( 'ivory-style', IVORY_ASSETS_URL . '/css/style.v3.css', array(), '3' );
	wp_enqueue_script( 'ivory-main', IVORY_ASSETS_URL . '/js/main.js', array(), '1', true );
}, 20 );

add_action( 'wp_head', function () {
	echo '<link rel="icon" href="' . esc_url( IVORY_ASSETS_URL . '/img/favicon.svg' ) . '" type="image/svg+xml">' . "\n";
	echo '<link rel="apple-touch-icon" href="' . esc_url( IVORY_ASSETS_URL . '/img/apple-touch-icon.png' ) . '">' . "\n";
}, 2 );

/* ---------------- Exact per-page SEO ---------------- */

function ivory_current_slug() {
	if ( is_front_page() ) {
		return 'home';
	}
	if ( is_page() ) {
		$post = get_queried_object();
		if ( $post && isset( $post->post_name ) ) {
			return $post->post_name;
		}
	}
	return '';
}

add_filter( 'pre_get_document_title', function ( $title ) {
	$slug = ivory_current_slug();
	$seo  = ivory_seo_map();
	if ( $slug && ! empty( $seo[ $slug ]['title'] ) ) {
		return $seo[ $slug ]['title'];
	}
	return $title;
}, 99 );

remove_action( 'wp_head', 'rel_canonical' );

add_action( 'wp_head', function () {
	$slug = ivory_current_slug();
	$seo  = ivory_seo_map();
	if ( ! $slug || empty( $seo[ $slug ] ) ) {
		return;
	}
	$data = $seo[ $slug ];
	echo "\n<!-- Ivory Digital SEO -->\n";
	if ( ! empty( $data['canonical'] ) ) {
		echo '<link rel="canonical" href="' . esc_url( $data['canonical'] ) . '">' . "\n";
	}
	if ( ! empty( $data['metas'] ) && is_array( $data['metas'] ) ) {
		foreach ( $data['metas'] as $tag ) {
			echo $tag . "\n";
		}
	}
	if ( ! empty( $data['jsonld'] ) && is_array( $data['jsonld'] ) ) {
		foreach ( $data['jsonld'] as $block ) {
			echo $block . "\n";
		}
	}
	echo "<!-- /Ivory Digital SEO -->\n";
}, 3 );

/* ---------------- root files ---------------- */

add_filter( 'robots_txt', function ( $output, $public ) {
	$file = IVORY_DIR . 'data/robots.txt';
	return file_exists( $file ) ? file_get_contents( $file ) : $output;
}, 10, 2 );

add_action( 'init', function () {
	$uri = isset( $_SERVER['REQUEST_URI'] ) ? parse_url( $_SERVER['REQUEST_URI'], PHP_URL_PATH ) : '';
	$uri = trim( (string) $uri, '/' );
	$serve = array(
		'llms.txt'      => array( 'data/llms.txt', 'text/plain; charset=utf-8' ),
		'llms_full.txt' => array( 'data/llms_full.txt', 'text/plain; charset=utf-8' ),
		'sitemap.xml'   => array( 'data/sitemap.xml', 'application/xml; charset=utf-8' ),
	);
	if ( isset( $serve[ $uri ] ) ) {
		$file = IVORY_DIR . $serve[ $uri ][0];
		if ( file_exists( $file ) ) {
			header( 'Content-Type: ' . $serve[ $uri ][1] );
			echo file_get_contents( $file );
			exit;
		}
	}
} );

/* ---------------- Admin ---------------- */

add_action( 'admin_notices', function () {
	if ( ! ivory_elementor_active() ) {
		echo '<div class="notice notice-error"><p><strong>Ivory Digital Website</strong> requires the free <strong>Elementor</strong> plugin to be installed and active.</p></div>';
	}
} );

add_action( 'admin_menu', function () {
	add_menu_page( 'Ivory Digital Website', 'Ivory Digital', 'manage_options', 'ivory-digital', 'ivory_admin_page', 'dashicons-admin-site-alt3', 58 );
} );

function ivory_admin_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	$msg = '';
	if ( isset( $_POST['ivory_action'] ) && check_admin_referer( 'ivory_import' ) ) {
		$force  = ( $_POST['ivory_action'] === 'reimport' );
		$result = ivory_import_all( $force );
		if ( is_wp_error( $result ) ) {
			$msg = '<div class="notice notice-error"><p>' . esc_html( $result->get_error_message() ) . '</p></div>';
		} else {
			$msg = '<div class="notice notice-success"><p><strong>Done!</strong> ' . count( $result ) . ' pages imported. The home page is set as your front page.</p></div>';
		}
	}
	$map      = get_option( IVORY_MAP_OPTION, array() );
	$manifest = ivory_manifest();

	echo '<div class="wrap"><h1>Ivory Digital &mdash; Website Importer</h1>';
	echo wp_kses_post( $msg );
	if ( ! ivory_elementor_active() ) {
		echo '<p style="color:#b32d2e;"><strong>Elementor is not active.</strong> Install &amp; activate Elementor, then import.</p>';
	}
	echo '<p>Imports all pages with the exact original design, editable in Elementor, plus full SEO, schema, <code>robots.txt</code>, <code>sitemap.xml</code> and <code>llms.txt</code>.</p>';

	echo '<form method="post" style="margin:16px 0;">';
	wp_nonce_field( 'ivory_import' );
	if ( empty( $map ) ) {
		echo '<input type="hidden" name="ivory_action" value="import">';
		submit_button( 'Import Website Now' );
	} else {
		echo '<input type="hidden" name="ivory_action" value="reimport">';
		submit_button( 'Re-import / Reset Pages', 'secondary' );
		echo '<p><em>Re-import overwrites the imported pages with the original design (manual edits to those pages are replaced).</em></p>';
	}
	echo '</form>';

	if ( ! empty( $map ) ) {
		echo '<h2>Imported pages</h2><table class="widefat striped" style="max-width:820px;"><thead><tr><th>Page</th><th>URL</th><th>Edit</th></tr></thead><tbody>';
		foreach ( $manifest['order'] as $slug ) {
			if ( empty( $map[ $slug ] ) ) {
				continue;
			}
			$pid   = $map[ $slug ];
			$view  = get_permalink( $pid );
			$edit  = admin_url( 'post.php?post=' . $pid . '&action=elementor' );
			$title = isset( $manifest['pages'][ $slug ]['title'] ) ? $manifest['pages'][ $slug ]['title'] : $slug;
			echo '<tr><td>' . esc_html( $title ) . '</td>';
			echo '<td><a href="' . esc_url( $view ) . '" target="_blank">' . esc_html( $slug === 'home' ? '/' : '/' . $slug . '/' ) . '</a></td>';
			echo '<td><a class="button button-small" href="' . esc_url( $edit ) . '">Edit with Elementor</a></td></tr>';
		}
		echo '</tbody></table>';
		echo '<p style="margin-top:14px;"><a class="button button-primary" href="' . esc_url( home_url( '/' ) ) . '" target="_blank">View Website</a> ';
		echo '<a class="button" href="' . esc_url( admin_url( 'options-permalink.php' ) ) . '">Permalink settings</a></p>';
	}
	echo '</div>';
}
