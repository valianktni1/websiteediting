<?php
/**
 * Plugin Name:       Wife To Be - Website (Elementor)
 * Description:        Imports the full Wife To Be website (all pages) as Elementor-editable pages with pixel-exact design and complete SEO, schema, robots.txt, sitemap.xml, llms.txt and llms-full.txt. Requires Elementor.
 * Version:           1.0.0
 * Author:            Wife To Be
 * License:           GPL-2.0+
 * Text Domain:       wifetobe
 * Requires Plugins:  elementor
 */

if ( ! defined( 'ABSPATH' ) ) { exit; }

define( 'WTB_DIR', plugin_dir_path( __FILE__ ) );
define( 'WTB_URL', plugin_dir_url( __FILE__ ) );
define( 'WTB_BASE_URL', rtrim( WTB_URL, '/' ) );
define( 'WTB_ASSETS_URL', WTB_BASE_URL . '/assets' );
define( 'WTB_BASE_TOKEN', '__WTB_BASE__' );
define( 'WTB_MAP_OPTION', 'wtb_imported_map' );
define( 'WTB_VERSION', '1.0.0' );
define( 'WTB_VER_OPTION', 'wtb_plugin_version' );

function wtb_elementor_active() { return did_action( 'elementor/loaded' ) || defined( 'ELEMENTOR_VERSION' ); }

function wtb_read_json( $rel ) {
	$p = WTB_DIR . $rel;
	return file_exists( $p ) ? json_decode( file_get_contents( $p ), true ) : null;
}
function wtb_manifest() { $m = wtb_read_json( 'data/manifest.json' ); return $m ? $m : array('order'=>array(),'pages'=>array()); }
function wtb_seo_map() { static $s=null; if($s===null){ $s=wtb_read_json('data/seo.json'); if(!is_array($s))$s=array(); } return $s; }

function wtb_apply_meta( $post_id, $content, $page_settings ) {
	$json = str_replace( WTB_BASE_TOKEN, WTB_BASE_URL, wp_json_encode( $content ) );
	update_post_meta( $post_id, '_elementor_data', wp_slash( $json ) );
	update_post_meta( $post_id, '_elementor_edit_mode', 'builder' );
	update_post_meta( $post_id, '_elementor_template_type', 'wp-page' );
	update_post_meta( $post_id, '_wp_page_template', 'elementor_canvas' );
	if ( defined( 'ELEMENTOR_VERSION' ) ) update_post_meta( $post_id, '_elementor_version', ELEMENTOR_VERSION );
	if ( ! empty( $page_settings ) ) update_post_meta( $post_id, '_elementor_page_settings', $page_settings );
}

function wtb_import_all( $force = false ) {
	if ( ! wtb_elementor_active() ) return new WP_Error( 'no-elementor', 'Elementor is not active.' );
	$manifest = wtb_manifest();
	$map = get_option( WTB_MAP_OPTION, array() ); if ( ! is_array( $map ) ) $map = array();
	foreach ( $manifest['order'] as $slug ) {
		$doc = wtb_read_json( 'templates/' . $slug . '.json' );
		if ( ! $doc || empty( $doc['content'] ) ) continue;
		$existing = isset( $map[ $slug ] ) ? get_post( $map[ $slug ] ) : null;
		if ( $existing && ! $force ) continue;
		if ( $existing && $force ) {
			$post_id = $existing->ID;
			wp_update_post( array( 'ID' => $post_id, 'post_title' => $doc['title'] ) );
		} else {
			$post_id = wp_insert_post( array( 'post_title'=>$doc['title'], 'post_name'=>$slug, 'post_status'=>'publish', 'post_type'=>'page' ) );
		}
		if ( is_wp_error( $post_id ) || ! $post_id ) continue;
		wtb_apply_meta( $post_id, $doc['content'], isset($doc['page_settings'])?$doc['page_settings']:array() );
		$map[ $slug ] = $post_id;
	}
	update_option( WTB_MAP_OPTION, $map );
	if ( ! empty( $map['home'] ) ) { update_option('show_on_front','page'); update_option('page_on_front',$map['home']); }
	if ( ! get_option( 'permalink_structure' ) ) update_option( 'permalink_structure', '/%postname%/' );
	flush_rewrite_rules();
	if ( class_exists( '\Elementor\Plugin' ) ) { try { \Elementor\Plugin::$instance->files_manager->clear_cache(); } catch ( \Throwable $e ) {} }
	return $map;
}

register_activation_hook( __FILE__, function () {
	if ( wtb_elementor_active() ) { $prev=get_option(WTB_VER_OPTION); wtb_import_all( $prev !== WTB_VERSION ); update_option(WTB_VER_OPTION, WTB_VERSION); }
	flush_rewrite_rules();
} );
add_action( 'init', function () {
	if ( ! is_admin() || ! wtb_elementor_active() ) return;
	if ( get_option( WTB_VER_OPTION ) !== WTB_VERSION ) { wtb_import_all( true ); update_option( WTB_VER_OPTION, WTB_VERSION ); }
}, 5 );

add_action( 'wp_enqueue_scripts', function () {
	wp_enqueue_style( 'wtb-fonts', 'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Jost:wght@300;400;500&family=Pinyon+Script&display=swap', array(), null );
	wp_enqueue_style( 'wtb-style', WTB_ASSETS_URL . '/styles.css', array(), '1' );
	wp_enqueue_script( 'wtb-main', WTB_ASSETS_URL . '/main.js', array(), '1', true );
}, 20 );

add_action( 'wp_head', function () {
	echo '<link rel="icon" type="image/png" href="' . esc_url( WTB_ASSETS_URL . '/favicon.png' ) . '">' . "\n";
	echo '<link rel="apple-touch-icon" href="' . esc_url( WTB_ASSETS_URL . '/favicon.png' ) . '">' . "\n";
}, 2 );

function wtb_current_slug() {
	if ( is_front_page() ) return 'home';
	if ( is_page() ) { $p = get_queried_object(); if ( $p && isset( $p->post_name ) ) return $p->post_name; }
	return '';
}
add_filter( 'pre_get_document_title', function ( $title ) {
	$slug = wtb_current_slug(); $seo = wtb_seo_map();
	if ( $slug && ! empty( $seo[ $slug ]['title'] ) ) return $seo[ $slug ]['title'];
	return $title;
}, 99 );
remove_action( 'wp_head', 'rel_canonical' );
add_action( 'wp_head', function () {
	$slug = wtb_current_slug(); $seo = wtb_seo_map();
	if ( ! $slug || empty( $seo[ $slug ] ) ) return;
	$d = $seo[ $slug ];
	echo "\n<!-- Wife To Be SEO -->\n";
	if ( ! empty( $d['canonical'] ) ) echo '<link rel="canonical" href="' . esc_url( $d['canonical'] ) . '">' . "\n";
	if ( ! empty( $d['metas'] ) ) foreach ( $d['metas'] as $t ) echo $t . "\n";
	if ( ! empty( $d['jsonld'] ) ) foreach ( $d['jsonld'] as $b ) echo $b . "\n";
	echo "<!-- /Wife To Be SEO -->\n";
}, 3 );

// Guarantee exactly one <title> (some block themes + Elementor Canvas emit two).
add_action( 'template_redirect', function () {
	if ( is_admin() || ! wtb_current_slug() ) return;
	ob_start( function ( $html ) {
		$n = 0;
		return preg_replace_callback( '#<title\b[^>]*>.*?</title>#is', function ( $m ) use ( &$n ) {
			$n++; return $n === 1 ? $m[0] : '';
		}, $html );
	} );
}, 1 );

add_filter( 'robots_txt', function ( $out, $public ) {
	$f = WTB_DIR . 'data/robots.txt';
	return file_exists( $f ) ? file_get_contents( $f ) : $out;
}, 10, 2 );
add_action( 'init', function () {
	$uri = isset( $_SERVER['REQUEST_URI'] ) ? parse_url( $_SERVER['REQUEST_URI'], PHP_URL_PATH ) : '';
	$uri = trim( (string) $uri, '/' );
	$serve = array(
		'llms.txt'      => array( 'data/llms.txt', 'text/plain; charset=utf-8' ),
		'llms-full.txt' => array( 'data/llms-full.txt', 'text/plain; charset=utf-8' ),
		'sitemap.xml'   => array( 'data/sitemap.xml', 'application/xml; charset=utf-8' ),
	);
	if ( isset( $serve[ $uri ] ) ) {
		$f = WTB_DIR . $serve[ $uri ][0];
		if ( file_exists( $f ) ) { header( 'Content-Type: ' . $serve[ $uri ][1] ); echo file_get_contents( $f ); exit; }
	}
} );

add_action( 'admin_notices', function () {
	if ( ! wtb_elementor_active() ) echo '<div class="notice notice-error"><p><strong>Wife To Be Website</strong> requires the free <strong>Elementor</strong> plugin.</p></div>';
} );
add_action( 'admin_menu', function () {
	add_menu_page( 'Wife To Be Website', 'Wife To Be', 'manage_options', 'wifetobe', 'wtb_admin_page', 'dashicons-heart', 59 );
} );
function wtb_admin_page() {
	if ( ! current_user_can( 'manage_options' ) ) return;
	$msg='';
	if ( isset($_POST['wtb_action']) && check_admin_referer('wtb_import') ) {
		$r = wtb_import_all( $_POST['wtb_action']==='reimport' );
		$msg = is_wp_error($r) ? '<div class="notice notice-error"><p>'.esc_html($r->get_error_message()).'</p></div>'
			: '<div class="notice notice-success"><p><strong>Done!</strong> '.count($r).' pages imported. Home set as front page.</p></div>';
	}
	$map=get_option(WTB_MAP_OPTION,array()); $manifest=wtb_manifest();
	echo '<div class="wrap"><h1>Wife To Be &mdash; Website Importer</h1>'.wp_kses_post($msg);
	if ( ! wtb_elementor_active() ) echo '<p style="color:#b32d2e;"><strong>Elementor is not active.</strong></p>';
	echo '<p>Imports all pages with the exact original design, editable in Elementor, plus full SEO, schema, <code>robots.txt</code>, <code>sitemap.xml</code>, <code>llms.txt</code> and <code>llms-full.txt</code>.</p>';
	echo '<form method="post" style="margin:16px 0;">'; wp_nonce_field('wtb_import');
	if ( empty($map) ) { echo '<input type="hidden" name="wtb_action" value="import">'; submit_button('Import Website Now'); }
	else { echo '<input type="hidden" name="wtb_action" value="reimport">'; submit_button('Re-import / Reset Pages','secondary'); }
	echo '</form>';
	if ( ! empty($map) ) {
		echo '<table class="widefat striped" style="max-width:820px;"><thead><tr><th>Page</th><th>URL</th><th>Edit</th></tr></thead><tbody>';
		foreach ( $manifest['order'] as $slug ) {
			if ( empty($map[$slug]) ) continue;
			$pid=$map[$slug];
			echo '<tr><td>'.esc_html($manifest['pages'][$slug]['title']??$slug).'</td><td><a href="'.esc_url(get_permalink($pid)).'" target="_blank">'.esc_html($slug==='home'?'/':'/'.$slug.'/').'</a></td><td><a class="button button-small" href="'.esc_url(admin_url('post.php?post='.$pid.'&action=elementor')).'">Edit with Elementor</a></td></tr>';
		}
		echo '</tbody></table><p style="margin-top:14px;"><a class="button button-primary" href="'.esc_url(home_url('/')).'" target="_blank">View Website</a></p>';
	}
	echo '</div>';
}
